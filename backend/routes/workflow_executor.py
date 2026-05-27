"""
Native Workflow Executor — Task Force AI

Runs translated React Flow JSON workflows on our FastAPI stack.
Walks the DAG in topological order, executing nodes via dedicated handlers.
All execution gated by compute credits and protected by SSRF/sandbox layers.

Node handlers (v1 coverage):
    - trigger          : emits initial input payload
    - http_request     : SSRF-protected outbound HTTP via lib/executor_security
    - condition        : safe expression evaluation, branches to true/false target
    - transform        : RestrictedPython sandbox via lib/workflow_sandbox
    - llm              : Gemini 2.5 Flash via Emergent LLM Key (platform-managed)
    - webhook (outbound): SSRF-protected outbound POST
    - action / database (v1): logged stub (returns INPUT unchanged, marked "not_executed_v1")
"""
import os
import json
import uuid
import asyncio
import httpx
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from dotenv import load_dotenv

from lib.compute_credits import check_compute_credits, increment_compute_usage
from lib.executor_security import validate_url
from lib.workflow_sandbox import execute_sandboxed

load_dotenv()

router = APIRouter()

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
MAX_NODES_PER_RUN = 50
HTTP_TIMEOUT = 15


def get_current_user():
    from server import get_current_user as _u
    return _u


def get_db():
    from server import db
    return db


# ─────────────────────────────────────────────────────────────
# DAG utilities
# ─────────────────────────────────────────────────────────────
def topological_sort(nodes: List[Dict], edges: List[Dict]) -> List[Dict]:
    """Topological sort with cycle detection. Returns ordered list of nodes."""
    node_map = {n["id"]: n for n in nodes}
    in_degree = {n["id"]: 0 for n in nodes}
    adj: Dict[str, List[str]] = {n["id"]: [] for n in nodes}

    for e in edges:
        src = e.get("from") or e.get("source")
        tgt = e.get("to") or e.get("target")
        if src in node_map and tgt in node_map:
            adj[src].append(tgt)
            in_degree[tgt] += 1

    # Kahn's algorithm
    queue = [nid for nid, deg in in_degree.items() if deg == 0]
    order = []
    while queue:
        nid = queue.pop(0)
        order.append(node_map[nid])
        for child in adj[nid]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    if len(order) != len(nodes):
        raise HTTPException(status_code=400, detail="Workflow contains a cycle. DAG required.")
    return order


# ─────────────────────────────────────────────────────────────
# Node Handlers
# ─────────────────────────────────────────────────────────────
async def _handle_trigger(node: Dict, prev_output: Any) -> Dict[str, Any]:
    data = node.get("data", {})
    payload = data.get("payload") or prev_output or {"triggered_at": datetime.now(timezone.utc).isoformat()}
    return {"status": "ok", "output": payload, "log": f"Trigger fired ({data.get('source', 'manual')})"}


async def _handle_http_request(node: Dict, prev_output: Any) -> Dict[str, Any]:
    data = node.get("data", {})
    url = data.get("url", "")
    method = (data.get("method") or "GET").upper()
    headers = data.get("headers", {}) or {}
    body = data.get("body") or prev_output

    if not url:
        return {"status": "error", "output": None, "log": "No URL configured."}

    validation = validate_url(url)
    if not validation["safe"]:
        return {"status": "error", "output": None, "log": f"SSRF blocked: {validation['reason']}"}

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=False) as client:
            req_kwargs = {"headers": headers}
            if method in ("POST", "PUT", "PATCH") and body:
                if isinstance(body, (dict, list)):
                    req_kwargs["json"] = body
                else:
                    req_kwargs["content"] = str(body)
            res = await client.request(method, url, **req_kwargs)
            text_preview = res.text[:5000]
            try:
                parsed = res.json()
            except Exception:
                parsed = text_preview
            return {
                "status": "ok" if res.status_code < 400 else "error",
                "output": parsed,
                "log": f"{method} {url} → {res.status_code}",
                "http_status": res.status_code,
            }
    except Exception as e:
        return {"status": "error", "output": None, "log": f"HTTP error: {str(e)[:200]}"}


def _safe_eval_condition(expr: str, context: Dict) -> bool:
    """Evaluate a condition safely via the sandbox."""
    if not expr or expr in ("true", "True", "1"):
        return True
    if expr in ("false", "False", "0"):
        return False
    code = f"RESULT = bool({expr})"
    result = execute_sandboxed(code, input_data=context, timeout=5)
    if result.get("success"):
        return bool(result.get("result"))
    return False


async def _handle_condition(node: Dict, prev_output: Any) -> Dict[str, Any]:
    data = node.get("data", {})
    expr = data.get("condition", "true")
    context = prev_output if isinstance(prev_output, dict) else {"INPUT": prev_output}
    branch = _safe_eval_condition(expr, context)
    return {
        "status": "ok",
        "output": prev_output,
        "branch": "true" if branch else "false",
        "log": f"Condition '{expr}' → {branch}",
    }


async def _handle_transform(node: Dict, prev_output: Any) -> Dict[str, Any]:
    data = node.get("data", {})
    code = data.get("code", "RESULT = INPUT")
    result = execute_sandboxed(code, input_data=prev_output, timeout=10)
    if result.get("success"):
        return {
            "status": "ok",
            "output": result.get("result") if result.get("result") is not None else prev_output,
            "log": f"Transform executed in {result.get('duration_ms', 0)}ms",
        }
    return {"status": "error", "output": None, "log": f"Transform failed: {result.get('error', 'unknown')}"}


async def _handle_llm(node: Dict, prev_output: Any) -> Dict[str, Any]:
    """LLM node — always uses platform Gemini 2.5 Flash via Emergent LLM Key."""
    if not EMERGENT_LLM_KEY:
        return {"status": "error", "output": None, "log": "Emergent LLM Key not configured."}

    data = node.get("data", {})
    prompt_template = data.get("prompt", "Summarize the input.")
    # Inject previous output into prompt
    if isinstance(prev_output, (dict, list)):
        input_str = json.dumps(prev_output)[:3000]
    else:
        input_str = str(prev_output or "")[:3000]

    user_message = f"{prompt_template}\n\nINPUT DATA:\n{input_str}"

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"workflow-{node.get('id', uuid.uuid4().hex[:8])}",
            system_message="You are a workflow node. Respond concisely with structured output.",
        )
        chat.with_model("gemini", "gemini-2.5-flash")
        msg = UserMessage(text=user_message)
        response = await chat.send_message(msg)
        return {
            "status": "ok",
            "output": {"llm_response": response, "model": "gemini-2.5-flash"},
            "log": f"LLM responded ({len(response)} chars)",
        }
    except Exception as e:
        return {"status": "error", "output": None, "log": f"LLM error: {str(e)[:200]}"}


async def _handle_webhook(node: Dict, prev_output: Any) -> Dict[str, Any]:
    """Outbound webhook (push to user-provided URL)."""
    data = node.get("data", {})
    url = data.get("url", "")
    if not url:
        # Inbound webhook — just pass-through
        return {"status": "ok", "output": prev_output, "log": "Webhook (inbound stub)"}

    validation = validate_url(url)
    if not validation["safe"]:
        return {"status": "error", "output": None, "log": f"SSRF blocked: {validation['reason']}"}

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=False) as client:
            res = await client.post(url, json=prev_output if isinstance(prev_output, (dict, list)) else {"data": prev_output})
            return {
                "status": "ok" if res.status_code < 400 else "error",
                "output": {"webhook_delivered": True, "http_status": res.status_code},
                "log": f"Webhook POST {url} → {res.status_code}",
            }
    except Exception as e:
        return {"status": "error", "output": None, "log": f"Webhook error: {str(e)[:200]}"}


async def _handle_stub(node: Dict, prev_output: Any, node_type: str) -> Dict[str, Any]:
    """Logged stub for v1-unsupported nodes (action, database)."""
    return {
        "status": "skipped",
        "output": prev_output,
        "log": f"[{node_type}] not executed in v1 — pass-through",
        "not_executed_v1": True,
    }


HANDLERS = {
    "trigger": _handle_trigger,
    "http_request": _handle_http_request,
    "condition": _handle_condition,
    "transform": _handle_transform,
    "llm": _handle_llm,
    "webhook": _handle_webhook,
}


# ─────────────────────────────────────────────────────────────
# Execution engine
# ─────────────────────────────────────────────────────────────
async def execute_workflow_dag(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a workflow's nodes in topological order. Returns trace + final output."""
    nodes = workflow.get("nodes", []) or []
    edges = workflow.get("edges", []) or []

    if not nodes:
        return {"success": False, "error": "Empty workflow.", "node_results": []}
    if len(nodes) > MAX_NODES_PER_RUN:
        return {"success": False, "error": f"Workflow exceeds {MAX_NODES_PER_RUN} node limit.", "node_results": []}

    order = topological_sort(nodes, edges)
    node_results: List[Dict[str, Any]] = []
    prev_output: Any = None
    started = datetime.now(timezone.utc)

    # Track edges by source for condition branching
    edges_by_source: Dict[str, List[Dict]] = {}
    for e in edges:
        src = e.get("from") or e.get("source")
        edges_by_source.setdefault(src, []).append(e)

    # For pipeline: track per-node output by id
    outputs_by_id: Dict[str, Any] = {}
    # Predecessors map
    preds: Dict[str, List[str]] = {n["id"]: [] for n in nodes}
    for e in edges:
        s = e.get("from") or e.get("source")
        t = e.get("to") or e.get("target")
        if s and t and t in preds:
            preds[t].append(s)

    skipped_ids: set = set()

    for node in order:
        # If all predecessors were skipped, skip this one too
        if preds[node["id"]] and all(p in skipped_ids for p in preds[node["id"]]):
            skipped_ids.add(node["id"])
            node_results.append({
                "node_id": node["id"], "type": node["type"],
                "status": "skipped", "log": "All upstream nodes skipped.",
                "duration_ms": 0,
            })
            continue

        # Compose input from this node's predecessors
        pred_outputs = [outputs_by_id.get(p) for p in preds[node["id"]] if p in outputs_by_id]
        node_input = pred_outputs[-1] if pred_outputs else prev_output

        ntype = node.get("type", "action")
        handler = HANDLERS.get(ntype)
        node_start = datetime.now(timezone.utc)
        try:
            if handler:
                res = await handler(node, node_input)
            else:
                res = await _handle_stub(node, node_input, ntype)
        except Exception as e:
            res = {"status": "error", "output": None, "log": f"Handler crash: {str(e)[:200]}"}

        duration_ms = int((datetime.now(timezone.utc) - node_start).total_seconds() * 1000)
        outputs_by_id[node["id"]] = res.get("output")
        prev_output = res.get("output")
        node_results.append({
            "node_id": node["id"],
            "type": ntype,
            "label": node.get("sub") or node.get("label"),
            "status": res.get("status"),
            "log": res.get("log"),
            "branch": res.get("branch"),
            "duration_ms": duration_ms,
        })

        # On error, halt execution
        if res.get("status") == "error":
            break

    total_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    success = all(r["status"] in ("ok", "skipped") for r in node_results)
    return {
        "success": success,
        "node_results": node_results,
        "final_output": prev_output,
        "duration_ms": total_ms,
    }


# ─────────────────────────────────────────────────────────────
# Routes — Templates (read-only catalog)
# ─────────────────────────────────────────────────────────────
@router.get("/workflows/templates")
async def list_templates(
    category: Optional[str] = None,
    limit: int = 100,
    user=Depends(get_current_user()),
):
    """List ingested n8n templates available in the Exchange."""
    db = get_db()
    query = {}
    if category:
        query["category"] = category
    cursor = db.n8n_templates.find(query, {"_id": 0}).sort("node_count", 1).limit(limit)
    templates = await cursor.to_list(limit)
    return {"templates": templates, "count": len(templates)}


@router.get("/workflows/templates/{template_id}")
async def get_template(template_id: str, user=Depends(get_current_user())):
    db = get_db()
    tpl = await db.n8n_templates.find_one({"source_hash": template_id}, {"_id": 0})
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found.")
    return tpl


@router.post("/workflows/templates/{template_id}/fork")
async def fork_template(template_id: str, user=Depends(get_current_user())):
    """Fork a template into the user's workflow workspace."""
    db = get_db()
    tpl = await db.n8n_templates.find_one({"source_hash": template_id}, {"_id": 0})
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found.")

    user_id = str(user.get("id", user.get("email")))
    now = datetime.now(timezone.utc).isoformat()
    wf_id = uuid.uuid4().hex

    doc = {
        "id": wf_id,
        "user_id": user_id,
        "name": f"{tpl['name']} (forked)",
        "description": tpl.get("description", ""),
        "source_template": template_id,
        "nodes": tpl["nodes"],
        "edges": tpl["edges"],
        "created_at": now,
        "updated_at": now,
    }
    await db.user_workflows.insert_one(doc)
    doc.pop("_id", None)
    return {"success": True, "workflow": doc}


# ─────────────────────────────────────────────────────────────
# Routes — User Workflows CRUD
# ─────────────────────────────────────────────────────────────
@router.get("/workflows")
async def list_user_workflows(user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    cursor = db.user_workflows.find({"user_id": user_id}, {"_id": 0}).sort("updated_at", -1)
    workflows = await cursor.to_list(200)
    return {"workflows": workflows}


@router.get("/workflows/{workflow_id}")
async def get_user_workflow(workflow_id: str, user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    wf = await db.user_workflows.find_one({"id": workflow_id, "user_id": user_id}, {"_id": 0})
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return wf


@router.delete("/workflows/{workflow_id}")
async def delete_user_workflow(workflow_id: str, user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    res = await db.user_workflows.delete_one({"id": workflow_id, "user_id": user_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return {"success": True}


# ─────────────────────────────────────────────────────────────
# Routes — Execute (compute-gated)
# ─────────────────────────────────────────────────────────────
@router.post("/workflows/{workflow_id}/execute")
async def execute_workflow_route(workflow_id: str, request: Request, user=Depends(get_current_user())):
    """
    Execute a user's workflow. Compute-credit gated.
    Returns 200 with allowed:false body when limit hit (k8s strips 403 body).
    """
    db = get_db()
    user_id = str(user.get("id", user.get("email")))

    wf = await db.user_workflows.find_one({"id": workflow_id, "user_id": user_id}, {"_id": 0})
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found.")

    # Gate 0: compute credits
    credit_check = await check_compute_credits(db, user)
    if credit_check.get("allowed") is False:
        return credit_check

    # Execute
    result = await execute_workflow_dag(wf)

    # Charge credit on dispatch
    await increment_compute_usage(db, user)

    # Log to MongoDB run history
    now = datetime.now(timezone.utc).isoformat()
    run_doc = {
        "id": uuid.uuid4().hex,
        "user_id": user_id,
        "workflow_id": workflow_id,
        "success": result["success"],
        "duration_ms": result["duration_ms"],
        "node_count": len(result["node_results"]),
        "final_output_preview": str(result.get("final_output"))[:500],
        "node_results": result["node_results"],
        "created_at": now,
    }
    await db.workflow_runs.insert_one(run_doc)
    run_doc.pop("_id", None)

    return {
        "success": result["success"],
        "run_id": run_doc["id"],
        "node_results": result["node_results"],
        "final_output": result.get("final_output"),
        "duration_ms": result["duration_ms"],
    }


@router.post("/workflows/templates/{template_id}/execute")
async def execute_template_route(template_id: str, request: Request, user=Depends(get_current_user())):
    """Execute a public template directly (dry-run, compute-gated)."""
    db = get_db()
    tpl = await db.n8n_templates.find_one({"source_hash": template_id}, {"_id": 0})
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found.")

    credit_check = await check_compute_credits(db, user)
    if credit_check.get("allowed") is False:
        return credit_check

    result = await execute_workflow_dag(tpl)
    await increment_compute_usage(db, user)
    return result


# ─────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────
@router.get("/workflows/engine/status")
async def engine_status(user=Depends(get_current_user())):
    db = get_db()
    template_count = await db.n8n_templates.count_documents({})
    return {
        "engine": "native-python",
        "version": "1.0.0",
        "supported_node_types": list(HANDLERS.keys()) + ["action (stub)", "database (stub)"],
        "templates_available": template_count,
        "max_nodes_per_run": MAX_NODES_PER_RUN,
        "llm_provider": "gemini-2.5-flash (platform)",
    }
