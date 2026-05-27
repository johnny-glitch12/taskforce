"""
Native Workflow Executor Router — Task Force AI

Routes:
    Templates:
        GET    /api/workflows/templates                  list catalog
        GET    /api/workflows/templates/{id}             single template
        POST   /api/workflows/templates/{id}/fork        copy into user_workflows
        POST   /api/workflows/templates/{id}/execute     direct compute-gated execute
    User Workflows:
        GET    /api/workflows                            list user's runtime workflows
        GET    /api/workflows/{id}                       single
        DELETE /api/workflows/{id}                       remove
        POST   /api/workflows/save                       upsert canvas → runtime
        PATCH  /api/workflows/{id}/nodes/{node_id}       deep-merge node data
        POST   /api/workflows/{id}/execute               sync execute (compute-gated)
        GET    /api/workflows/{id}/runs                  recent runs (paginated/lean)
        GET    /api/workflows/{id}/runs/{run_id}         single run detail (full node_results)
    Async dispatch (long-running):
        POST   /api/workflows/{id}/dispatch              enqueue, returns job_id
        GET    /api/workflows/jobs/{job_id}              poll job status
    BYOK credentials:
        GET    /api/workflows/credentials                list user's BYOK (encrypted-at-rest)
        POST   /api/workflows/credentials                upsert {service, api_key, extra}
        DELETE /api/workflows/credentials/{service}      remove
    Engine:
        GET    /api/workflows/engine/status
"""
import asyncio
import uuid
import httpx
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from lib.compute_credits import check_compute_credits, increment_compute_usage
from lib.workflow_handlers import HANDLERS, SUPPORTED_BYOK_SERVICES
from lib.byok_crypto import encrypt_key, decrypt_key
from lib.workflow_jobs import schedule_async_job

router = APIRouter()

MAX_NODES_PER_RUN = 50


def get_current_user():
    from server import get_current_user as _u
    return _u


def get_db():
    from server import db
    return db


# ─────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────
class BYOKCreate(BaseModel):
    service: Literal[
        "slack", "sendgrid", "gmail",
        "instagram", "stripe", "telegram", "discord", "notion", "gsheets",
        "twilio", "github", "openai", "anthropic", "postgres", "mongodb",
    ]
    api_key: str = Field(min_length=1, max_length=4096)
    extra: Dict[str, Any] = Field(default_factory=dict)


class NodePatchRequest(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("data")
    @classmethod
    def _bound_size(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if len(str(v)) > 50_000:
            raise ValueError("data payload exceeds 50KB limit.")
        return v


class SaveCanvasRequest(BaseModel):
    studio_workflow_id: str = Field(min_length=1, max_length=128)
    name: str = Field(default="Untitled Workflow", max_length=200)
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    source_template: Optional[str] = None

    @field_validator("studio_workflow_id")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("studio_workflow_id is required and must be non-empty.")
        return v


# ─────────────────────────────────────────────────────────────
# DAG utilities
# ─────────────────────────────────────────────────────────────
def topological_sort(nodes: List[Dict], edges: List[Dict]) -> List[Dict]:
    node_map = {n["id"]: n for n in nodes}
    in_degree = {n["id"]: 0 for n in nodes}
    adj: Dict[str, List[str]] = {n["id"]: [] for n in nodes}

    for e in edges:
        src = e.get("from") or e.get("source")
        tgt = e.get("to") or e.get("target")
        if src in node_map and tgt in node_map:
            adj[src].append(tgt)
            in_degree[tgt] += 1

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
# Execution engine
# ─────────────────────────────────────────────────────────────
async def execute_workflow_dag(workflow: Dict[str, Any], ctx: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Execute a workflow's nodes in topological order. Returns trace + final output."""
    nodes = workflow.get("nodes", []) or []
    edges = workflow.get("edges", []) or []
    ctx = ctx or {}

    if not nodes:
        return {"success": False, "error": "Empty workflow.", "node_results": [], "duration_ms": 0, "final_output": None}
    if len(nodes) > MAX_NODES_PER_RUN:
        return {"success": False, "error": f"Workflow exceeds {MAX_NODES_PER_RUN} node limit.", "node_results": [], "duration_ms": 0, "final_output": None}

    order = topological_sort(nodes, edges)
    node_results: List[Dict[str, Any]] = []
    prev_output: Any = None
    started = datetime.now(timezone.utc)

    preds: Dict[str, List[str]] = {n["id"]: [] for n in nodes}
    for e in edges:
        s = e.get("from") or e.get("source")
        t = e.get("to") or e.get("target")
        if s and t and t in preds:
            preds[t].append(s)

    outputs_by_id: Dict[str, Any] = {}
    skipped_ids: set = set()

    for node in order:
        if preds[node["id"]] and all(p in skipped_ids for p in preds[node["id"]]):
            skipped_ids.add(node["id"])
            node_results.append({
                "node_id": node["id"], "type": node["type"],
                "status": "skipped", "log": "All upstream nodes skipped.",
                "duration_ms": 0,
            })
            continue

        pred_outputs = [outputs_by_id.get(p) for p in preds[node["id"]] if p in outputs_by_id]
        node_input = pred_outputs[-1] if pred_outputs else prev_output

        ntype = node.get("type", "action")
        handler = HANDLERS.get(ntype)
        node_start = datetime.now(timezone.utc)
        try:
            if handler:
                res = await handler(node, node_input, ctx)
            else:
                res = {"status": "skipped", "output": node_input, "log": f"[{ntype}] no handler"}
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


async def _log_run(db, user_id: str, workflow_id: str | None, source: str, result: Dict) -> str:
    """Persist a workflow run to db.workflow_runs and return run_id."""
    run_id = uuid.uuid4().hex
    await db.workflow_runs.insert_one({
        "id": run_id,
        "user_id": user_id,
        "workflow_id": workflow_id,
        "source": source,  # "user_workflow" | "template" | "async"
        "success": result.get("success", False),
        "duration_ms": result.get("duration_ms", 0),
        "node_count": len(result.get("node_results", [])),
        "final_output_preview": str(result.get("final_output"))[:500],
        "node_results": result.get("node_results", []),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return run_id


def _build_ctx(db, user) -> Dict[str, Any]:
    return {
        "db": db,
        "user_id": str(user.get("id", user.get("email"))),
    }


# ─────────────────────────────────────────────────────────────
# Routes — Templates
# ─────────────────────────────────────────────────────────────
@router.get("/workflows/templates")
async def list_templates(
    category: Optional[str] = None,
    limit: int = 100,
    user=Depends(get_current_user()),
):
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
    # Exclude TEST_* fixtures from the user-facing list (testing-agent pollution shield).
    query = {"user_id": user_id, "name": {"$not": {"$regex": "^TEST_", "$options": "i"}}}
    cursor = db.user_workflows.find(query, {"_id": 0}).sort("updated_at", -1)
    workflows = await cursor.to_list(200)
    return {"workflows": workflows}


# ── Specific paths BEFORE the catch-all /workflows/{id} ──
@router.get("/workflows/credentials")
async def list_credentials(user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    creds = await db.byok_credentials.find({"user_id": user_id}, {"_id": 0}).to_list(50)
    masked = []
    for c in creds:
        # Decrypt only the last 4 chars for masking; keep encrypted at rest
        stored = c.get("api_key", "")
        plain = decrypt_key(stored)
        c["api_key_masked"] = ("•" * 8 + plain[-4:]) if len(plain) > 4 else "•" * max(len(plain), 1)
        c["encrypted"] = stored.startswith("enc:v1:")
        c.pop("api_key", None)
        masked.append(c)
    return {"credentials": masked, "supported_services": SUPPORTED_BYOK_SERVICES}


@router.post("/workflows/credentials")
async def save_credential(req: BYOKCreate, user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    now = datetime.now(timezone.utc).isoformat()

    encrypted = encrypt_key(req.api_key)

    await db.byok_credentials.update_one(
        {"user_id": user_id, "service": req.service},
        {
            "$set": {"api_key": encrypted, "extra": req.extra, "updated_at": now},
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return {"success": True, "service": req.service}


@router.delete("/workflows/credentials/{service}")
async def delete_credential(service: str, user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    res = await db.byok_credentials.delete_one({"user_id": user_id, "service": service.lower()})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Credential not found.")
    return {"success": True}


# Gmail OAuth routes moved to routes/gmail_oauth_routes.py


# ─────────────────────────────────────────────────────────────
# BYOK provider info (KMS abstraction)
# ─────────────────────────────────────────────────────────────
@router.get("/workflows/credentials/_provider")
async def get_byok_provider(user=Depends(get_current_user())):
    """Diagnostic — returns active BYOK encryption backend. Admin only."""
    if (user.get("role") or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    from lib.byok_crypto import provider_info
    return provider_info()


@router.get("/workflows/jobs/{job_id}")
async def get_job_status(job_id: str, user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    job = await db.workflow_jobs.find_one({"id": job_id, "user_id": user_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.get("/workflows/engine/status")
async def engine_status(user=Depends(get_current_user())):
    db = get_db()
    template_count = await db.n8n_templates.count_documents({})
    return {
        "engine": "native-python",
        "version": "1.1.0",
        "supported_node_types": list(HANDLERS.keys()),
        "byok_services": SUPPORTED_BYOK_SERVICES,
        "templates_available": template_count,
        "max_nodes_per_run": MAX_NODES_PER_RUN,
        "llm_provider": "gemini-2.5-flash (platform)",
        "async_dispatch": True,
    }


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


@router.post("/workflows/save")
async def save_canvas_to_runtime(req: SaveCanvasRequest, user=Depends(get_current_user())):
    """Idempotent upsert of canvas state into user_workflows, keyed by studio_workflow_id."""
    if len(req.nodes) > MAX_NODES_PER_RUN:
        raise HTTPException(status_code=400, detail=f"Workflow exceeds {MAX_NODES_PER_RUN} node limit.")

    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    now = datetime.now(timezone.utc).isoformat()

    existing = await db.user_workflows.find_one({"user_id": user_id, "studio_workflow_id": req.studio_workflow_id})

    if existing:
        await db.user_workflows.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "name": req.name, "nodes": req.nodes, "edges": req.edges,
                "source_template": req.source_template, "updated_at": now,
            }},
        )
        wf_id = existing["id"]
    else:
        wf_id = uuid.uuid4().hex
        await db.user_workflows.insert_one({
            "id": wf_id, "user_id": user_id, "studio_workflow_id": req.studio_workflow_id,
            "name": req.name, "nodes": req.nodes, "edges": req.edges,
            "source_template": req.source_template,
            "created_at": now, "updated_at": now,
        })

    return {"success": True, "workflow_id": wf_id}


@router.patch("/workflows/{workflow_id}/nodes/{node_id}")
async def update_node_data(workflow_id: str, node_id: str, req: NodePatchRequest, user=Depends(get_current_user())):
    """Deep-merge update of a single node's data dict. Returns 422 on bad input."""
    new_data = req.data

    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    wf = await db.user_workflows.find_one({"id": workflow_id, "user_id": user_id})
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found.")

    def _deep_merge(base: dict, patch: dict) -> dict:
        out = dict(base)
        for k, v in patch.items():
            if isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = _deep_merge(out[k], v)
            else:
                out[k] = v
        return out

    updated_nodes = []
    found = False
    for n in wf.get("nodes", []):
        if n.get("id") == node_id:
            n["data"] = _deep_merge(n.get("data", {}), new_data)
            found = True
        updated_nodes.append(n)

    if not found:
        raise HTTPException(status_code=404, detail="Node not found in workflow.")

    await db.user_workflows.update_one(
        {"_id": wf["_id"]},
        {"$set": {"nodes": updated_nodes, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"success": True, "node_id": node_id, "data": next(n["data"] for n in updated_nodes if n["id"] == node_id)}


# ─────────────────────────────────────────────────────────────
# Routes — Execute (sync, compute-gated)
# ─────────────────────────────────────────────────────────────
@router.post("/workflows/{workflow_id}/execute")
async def execute_workflow_route(workflow_id: str, request: Request, user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))

    wf = await db.user_workflows.find_one({"id": workflow_id, "user_id": user_id}, {"_id": 0})
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found.")

    credit_check = await check_compute_credits(db, user)
    if credit_check.get("allowed") is False:
        return credit_check

    ctx = _build_ctx(db, user)
    result = await execute_workflow_dag(wf, ctx)
    await increment_compute_usage(db, user)
    run_id = await _log_run(db, user_id, workflow_id, "user_workflow", result)

    return {
        "success": result["success"],
        "run_id": run_id,
        "node_results": result["node_results"],
        "final_output": result.get("final_output"),
        "duration_ms": result["duration_ms"],
    }


@router.post("/workflows/templates/{template_id}/execute")
async def execute_template_route(template_id: str, request: Request, user=Depends(get_current_user())):
    db = get_db()
    tpl = await db.n8n_templates.find_one({"source_hash": template_id}, {"_id": 0})
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found.")

    credit_check = await check_compute_credits(db, user)
    if credit_check.get("allowed") is False:
        return credit_check

    user_id = str(user.get("id", user.get("email")))
    ctx = _build_ctx(db, user)
    result = await execute_workflow_dag(tpl, ctx)
    await increment_compute_usage(db, user)
    # Log template direct-execute too (per P3 backlog)
    run_id = await _log_run(db, user_id, None, "template", result)
    return {**result, "run_id": run_id}


# ─────────────────────────────────────────────────────────────
# Routes — Async Dispatch (in-process asyncio worker via lib/workflow_jobs)
# ─────────────────────────────────────────────────────────────
@router.post("/workflows/{workflow_id}/dispatch")
async def dispatch_workflow_async(workflow_id: str, user=Depends(get_current_user())):
    """Enqueue async execution. Returns job_id immediately. Compute gate enforced on enqueue."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))

    wf = await db.user_workflows.find_one({"id": workflow_id, "user_id": user_id}, {"_id": 0})
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found.")

    credit_check = await check_compute_credits(db, user)
    if credit_check.get("allowed") is False:
        return credit_check

    job_id = uuid.uuid4().hex
    await db.workflow_jobs.insert_one({
        "id": job_id,
        "user_id": user_id,
        "workflow_id": workflow_id,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    schedule_async_job(job_id, workflow_id, user)
    return {"success": True, "job_id": job_id, "status": "queued"}


@router.get("/workflows/{workflow_id}/runs")
async def list_workflow_runs(
    workflow_id: str,
    limit: int = 20,
    skip: int = 0,
    user=Depends(get_current_user()),
):
    """List recent execution runs (LEAN — node_results stripped). Use /runs/{run_id} for full detail."""
    limit = max(1, min(limit, 100))
    skip = max(0, skip)
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    wf = await db.user_workflows.find_one({"id": workflow_id, "user_id": user_id}, {"_id": 0, "id": 1})
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found.")

    projection = {"_id": 0, "node_results": 0}  # strip heavy field
    cursor = db.workflow_runs.find(
        {"user_id": user_id, "workflow_id": workflow_id},
        projection,
    ).sort("created_at", -1).skip(skip).limit(limit)
    runs = await cursor.to_list(limit)
    total = await db.workflow_runs.count_documents({"user_id": user_id, "workflow_id": workflow_id})
    return {"runs": runs, "total": total, "limit": limit, "skip": skip}


@router.get("/workflows/{workflow_id}/runs/{run_id}")
async def get_workflow_run(workflow_id: str, run_id: str, user=Depends(get_current_user())):
    """Return full single run (includes node_results)."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    run = await db.workflow_runs.find_one(
        {"id": run_id, "workflow_id": workflow_id, "user_id": user_id},
        {"_id": 0},
    )
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    return run
