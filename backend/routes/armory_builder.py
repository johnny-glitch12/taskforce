"""
Armory AI Bot Builder — POST /api/armory/build-bot

Translates a natural-language prompt into a full bot package:
  - Visual React Flow manifest (nodes + edges)
  - Real source-code files (main.py, requirements.txt, README.md, ...)

Plus GitHub-style fork/save/commit for the project lifecycle.

Storage:
  - MongoDB collection `bot_projects` (single source of truth — pod is stateless)
  - Each commit appended to `commit_history[]` (forked_from records lineage
    for the 80/20 creator-revenue share).
"""
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lib.credit_wallet import can_afford as wallet_can_afford, debit as wallet_debit

router = APIRouter()

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
GEMINI_MODEL = "gemini-2.5-pro"


def get_current_user():
    from server import get_current_user as _u
    return _u


def get_db():
    from server import db
    return db


# ─── Schemas ──────────────────────────────────────────
class BuildBotRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=4000)
    project_id: Optional[str] = None  # if set → append a new commit to existing project


class FileObject(BaseModel):
    path: str = Field(min_length=1, max_length=200)
    content: str = Field(max_length=200_000)
    language: Optional[str] = None


class CommitRequest(BaseModel):
    message: str = Field(min_length=1, max_length=200)
    files: List[FileObject]
    nodes: Optional[list] = None
    edges: Optional[list] = None


class PatchFileRequest(BaseModel):
    path: str = Field(min_length=1, max_length=200)
    content: str = Field(max_length=200_000)


# ─── LLM prompt → structured bot package ──────────────
BUILDER_SYSTEM_PROMPT = """You are the Task Force AI Armory Compiler — an expert agent
architect that converts a user's natural-language description into a COMPLETE,
RUNNABLE bot package.

CRITICAL RULES — read carefully:
1. NEVER ask the user clarifying questions. NEVER reply with markdown text. NEVER use
   asterisks for bold. Your ONLY allowed output is a single valid JSON object.
2. Infer reasonable defaults for anything the user didn't specify.
3. NODE COUNT MUST SCALE WITH COMPLEXITY. Do NOT force exactly 3 nodes. Use:
       - Simple utility bots (calculator, formatter): 3-5 nodes
       - Standard automations (send email, post tweet, scrape): 5-8 nodes
       - Multi-service workflows (CRM → AI → Notification): 8-12 nodes
       - Complex multi-branch agents (with conditions, loops, error handlers): 12-25 nodes
   ALWAYS include explicit nodes for: validation/input-check, error handling, logging,
   formatting/transform steps, and notification/output. Branches with IF/Condition nodes
   are encouraged when there are multiple possible outcomes.
4. PRODUCE MULTIPLE CODE FILES when the bot is non-trivial. Split logic into
   modules (e.g. main.py + handlers.py + utils.py + config.py + requirements.txt +
   README.md + .env.example). Simple bots can still be 2-3 files.
5. Inject the actual Python code that implements each logical step into the matching
   node's `data.code` field for transform/condition nodes AND ALSO ship it as a real
   module file.
6. Use realistic service slugs in `data.service` for action nodes — e.g. "instagram",
   "slack", "stripe", "gmail", "openai", "twilio_sms", "shopify", "gsheets", "notion".

Output schema — return EXACTLY this JSON shape, no prose, no code fences:

{
  "name": "<short PascalCase bot name>",
  "description": "<one-sentence summary of what it does>",
  "language": "python",
  "files": [
    { "path": "main.py",          "language": "python",   "content": "<runnable entrypoint>" },
    { "path": "handlers.py",      "language": "python",   "content": "<extracted handler logic, if non-trivial>" },
    { "path": "utils.py",         "language": "python",   "content": "<helpers, if applicable>" },
    { "path": "config.py",        "language": "python",   "content": "<config + env reading>" },
    { "path": "requirements.txt", "language": "text",     "content": "<one pip package per line>" },
    { "path": ".env.example",     "language": "text",     "content": "<env keys with placeholder values>" },
    { "path": "README.md",        "language": "markdown", "content": "<plain text, NO asterisks or bold>" }
  ],
  "manifest": {
    "nodes": [
      { "id": "n1", "type": "trigger",   "label": "Trigger",    "sub": "<title>", "icon": "Mail",     "x": 80,   "y": 120, "data": { "source": "manual" } },
      { "id": "n2", "type": "transform", "label": "Validate",   "sub": "<title>", "icon": "Filter",   "x": 360,  "y": 120, "data": { "code": "..." } },
      { "id": "n3", "type": "http_request","label": "API Call", "sub": "<title>", "icon": "Globe",    "x": 640,  "y": 120, "data": { "method": "POST", "url": "" } },
      { "id": "n4", "type": "condition", "label": "Success?",   "sub": "<title>", "icon": "Split",    "x": 920,  "y": 120, "data": { "condition": "..." } },
      { "id": "n5", "type": "action",    "label": "Notify",     "sub": "<title>", "icon": "Send",     "x": 1200, "y": 60,  "data": { "service": "slack" } },
      { "id": "n6", "type": "action",    "label": "Error Log",  "sub": "<title>", "icon": "Bug",      "x": 1200, "y": 200, "data": { "service": "noop" } }
    ],
    "edges": [
      { "from": "n1", "to": "n2" },
      { "from": "n2", "to": "n3" },
      { "from": "n3", "to": "n4" },
      { "from": "n4", "to": "n5" },
      { "from": "n4", "to": "n6" }
    ]
  }
}

Allowed node types: trigger, llm, condition, action, http_request, webhook,
database, transform.
Allowed icons: Mail, Brain, Zap, FileText, MessageCircle, GitBranch, Database,
Globe, Filter, Code, Layers, Calendar, FileInput, Rss, CreditCard, Send, Hash,
Phone, Bug, Cloud, Twitter, Linkedin, Facebook, Instagram, Youtube, ShoppingBag,
Lock, Clock, Calculator, FolderOpen, Split, Combine, Repeat, Timer, Server,
BookOpen, Mic, Volume2, Image, Film, Table, Trello, CheckSquare, Building2,
Headphones, MessageSquare, Github, Gitlab, Bot, AtSign, Activity, AlertTriangle.

Coordinate layout: lay nodes left-to-right starting at x=80, step x by 280.
Use y=120 baseline; for branch alternates use y=60 (top) and y=200 (bottom).
Stagger longer pipelines vertically by ±60 to avoid edge collisions.

Strict output: a single JSON object. No ``` fences. No commentary."""


def _extract_json(text: str) -> dict:
    """Strip code fences / leading commentary and parse to JSON."""
    if not text:
        raise ValueError("Empty LLM response")
    s = text.strip()
    # Strip markdown code fences if present
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```\s*$", "", s)
    # If model added prose, grab the first {...} balanced block
    if not s.lstrip().startswith("{"):
        m = re.search(r"\{.*\}", s, re.DOTALL)
        if m:
            s = m.group(0)
    return json.loads(s)


def _strip_md(s: str) -> str:
    if not isinstance(s, str):
        return s
    return re.sub(r"\*\*(.*?)\*\*", r"\1", s).replace("__", "")


def _normalize_bot(payload: dict) -> dict:
    """Defensive normalization + markdown asterisk strip on user-visible strings."""
    if not isinstance(payload, dict):
        raise ValueError("Bot payload must be a JSON object")
    name = _strip_md(payload.get("name") or "Untitled Bot")[:80]
    description = _strip_md(payload.get("description") or "")[:600]
    files = []
    for f in (payload.get("files") or [])[:20]:
        if not isinstance(f, dict):
            continue
        path = (f.get("path") or "").strip()
        if not path or path.startswith("/") or ".." in path:
            continue
        files.append({
            "path": path[:200],
            "language": (f.get("language") or "text")[:32],
            "content": str(f.get("content") or "")[:200_000],
        })
    manifest = payload.get("manifest") or {}
    nodes = []
    for n in (manifest.get("nodes") or [])[:50]:
        if not isinstance(n, dict):
            continue
        nodes.append({
            "id": str(n.get("id") or f"n{len(nodes)+1}"),
            "type": n.get("type") or "transform",
            "label": _strip_md(n.get("label") or n.get("type") or "Node")[:40],
            "sub": _strip_md(n.get("sub") or "")[:80],
            "icon": n.get("icon") or "Zap",
            "x": int(n.get("x") or 80 + len(nodes) * 280),
            "y": int(n.get("y") or 120),
            "data": n.get("data") if isinstance(n.get("data"), dict) else {},
        })
    edges = []
    valid_ids = {n["id"] for n in nodes}
    for e in (manifest.get("edges") or [])[:100]:
        if not isinstance(e, dict):
            continue
        src = e.get("from") or e.get("source")
        dst = e.get("to") or e.get("target")
        if src in valid_ids and dst in valid_ids:
            edges.append({"from": src, "to": dst})
    return {
        "name": name,
        "description": description,
        "language": payload.get("language") or "python",
        "files": files,
        "manifest": {"nodes": nodes, "edges": edges},
    }


async def _generate_with_gemini(prompt: str) -> dict:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"armory-builder-{uuid.uuid4().hex[:8]}",
        system_message=BUILDER_SYSTEM_PROMPT,
    ).with_model("gemini", GEMINI_MODEL)
    msg = UserMessage(text=f"Build this bot now (JSON only, no prose):\n\n{prompt}")
    raw = await chat.send_message(msg)
    payload = _extract_json(raw)
    return _normalize_bot(payload)


# ─── POST /api/armory/build-bot ───────────────────────
@router.post("/armory/build-bot")
async def build_bot(req: BuildBotRequest, user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))

    # Credit wallet gate — Armory build costs 5 credits per bot.
    credit_check = await wallet_can_afford(db, user, "build_bot")
    if not credit_check.get("allowed"):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=402, content=credit_check)

    try:
        bot = await _generate_with_gemini(req.prompt)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM build failed: {str(e)[:200]}")

    if not bot["files"] or not bot["manifest"]["nodes"]:
        raise HTTPException(status_code=502, detail="Generated bot has no files or nodes — try a more specific prompt.")

    now = datetime.now(timezone.utc).isoformat()
    commit_id = uuid.uuid4().hex[:12]
    commit_entry = {
        "commit_id": commit_id,
        "message": f"build: {req.prompt[:140]}",
        "author": user.get("email"),
        "files": bot["files"],
        "nodes": bot["manifest"]["nodes"],
        "edges": bot["manifest"]["edges"],
        "created_at": now,
    }

    if req.project_id:
        existing = await db.bot_projects.find_one({"id": req.project_id, "user_id": user_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Project not found.")
        await db.bot_projects.update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "name": bot["name"] or existing["name"],
                    "description": bot["description"] or existing["description"],
                    "files": bot["files"],
                    "nodes": bot["manifest"]["nodes"],
                    "edges": bot["manifest"]["edges"],
                    "updated_at": now,
                },
                "$push": {"commit_history": commit_entry},
            },
        )
        project_id = req.project_id
    else:
        project_id = uuid.uuid4().hex
        doc = {
            "id": project_id,
            "user_id": user_id,
            "creator_email": user.get("email"),
            "name": bot["name"],
            "description": bot["description"],
            "language": bot["language"],
            "prompt": req.prompt,
            "files": bot["files"],
            "nodes": bot["manifest"]["nodes"],
            "edges": bot["manifest"]["edges"],
            "forked_from": None,
            "forked_from_creator": None,
            "commit_history": [commit_entry],
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
        await db.bot_projects.insert_one(doc)

    await wallet_debit(db, user, "build_bot", ref=project_id)

    project = await db.bot_projects.find_one({"id": project_id}, {"_id": 0})
    return {"success": True, "project_id": project_id, "project": project}


# ─── GitHub-style project CRUD ────────────────────────
@router.get("/armory/bot-projects")
async def list_bot_projects(user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    cursor = db.bot_projects.find(
        {"user_id": user_id},
        {"_id": 0, "commit_history": 0},  # lean list
    ).sort("updated_at", -1)
    projects = await cursor.to_list(100)
    return {"projects": projects}


@router.get("/armory/bot-projects/{project_id}")
async def get_bot_project(project_id: str, user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    doc = await db.bot_projects.find_one({"id": project_id, "user_id": user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found.")
    return doc


@router.delete("/armory/bot-projects/{project_id}")
async def delete_bot_project(project_id: str, user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    res = await db.bot_projects.delete_one({"id": project_id, "user_id": user_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found.")
    return {"success": True}


@router.post("/armory/bot-projects/{project_id}/commit")
async def commit_project(project_id: str, req: CommitRequest, user=Depends(get_current_user())):
    """Snapshot current files/nodes as a new version (GitHub-style)."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    doc = await db.bot_projects.find_one({"id": project_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found.")

    files = [f.model_dump() for f in req.files][:20]
    nodes = req.nodes if isinstance(req.nodes, list) else doc.get("nodes", [])
    edges = req.edges if isinstance(req.edges, list) else doc.get("edges", [])
    now = datetime.now(timezone.utc).isoformat()
    commit_entry = {
        "commit_id": uuid.uuid4().hex[:12],
        "message": req.message[:200],
        "author": user.get("email"),
        "files": files,
        "nodes": nodes,
        "edges": edges,
        "created_at": now,
    }
    await db.bot_projects.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "files": files,
                "nodes": nodes,
                "edges": edges,
                "updated_at": now,
            },
            "$inc": {"version": 1},
            "$push": {"commit_history": commit_entry},
        },
    )
    updated = await db.bot_projects.find_one({"id": project_id}, {"_id": 0})
    return {"success": True, "commit": commit_entry, "project": updated}


@router.patch("/armory/bot-projects/{project_id}/files")
async def patch_file(project_id: str, req: PatchFileRequest, user=Depends(get_current_user())):
    """In-place file edit (used by the Monaco code editor on Save)."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    doc = await db.bot_projects.find_one({"id": project_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found.")
    files = doc.get("files") or []
    replaced = False
    for f in files:
        if f.get("path") == req.path:
            f["content"] = req.content
            replaced = True
            break
    if not replaced:
        files.append({"path": req.path, "content": req.content, "language": "text"})
    await db.bot_projects.update_one(
        {"_id": doc["_id"]},
        {"$set": {"files": files, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"success": True, "files": files}


@router.post("/armory/bot-projects/{project_id}/fork")
async def fork_project(project_id: str, user=Depends(get_current_user())):
    """
    GitHub-style fork — INTENTIONALLY PUBLIC.

    Any authenticated user may fork ANY bot_project by id. This mirrors GitHub's
    fork model and is required for the 80/20 creator-revenue share: the
    `forked_from` + `forked_from_creator` fields preserve lineage so we always
    know which original creator gets royalties when a renter runs a modified
    bot. The original creator's project is NOT modified.

    If product later requires private projects, add a `visibility: 'public' |
    'private'` field on bot_projects and filter here.
    """
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    source = await db.bot_projects.find_one({"id": project_id})
    if not source:
        raise HTTPException(status_code=404, detail="Project not found.")
    new_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    forked = {
        "id": new_id,
        "user_id": user_id,
        "creator_email": user.get("email"),
        "name": f"{source['name']} (fork)",
        "description": source.get("description", ""),
        "language": source.get("language", "python"),
        "prompt": source.get("prompt", ""),
        "files": source.get("files", []),
        "nodes": source.get("nodes", []),
        "edges": source.get("edges", []),
        "forked_from": source["id"],
        "forked_from_creator": source.get("user_id"),
        "commit_history": [{
            "commit_id": uuid.uuid4().hex[:12],
            "message": f"fork from {source['name']}",
            "author": user.get("email"),
            "files": source.get("files", []),
            "nodes": source.get("nodes", []),
            "edges": source.get("edges", []),
            "created_at": now,
        }],
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }
    await db.bot_projects.insert_one(forked)
    forked.pop("_id", None)
    return {"success": True, "project_id": new_id, "project": forked}


@router.post("/armory/bot-projects/{project_id}/test-run")
async def test_run_project(project_id: str, user=Depends(get_current_user())):
    """One-shot dry-run of a bot project's node DAG. Re-uses the existing
    workflow executor and the dual-pool credit_wallet.debit() — atomic,
    race-safe, and visible in /api/credits/me."""
    from routes.workflow_executor import execute_workflow_dag, _build_ctx, _log_run
    from lib.credit_wallet import can_afford, debit

    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    project = await db.bot_projects.find_one({"id": project_id, "user_id": user_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    if not project.get("nodes"):
        raise HTTPException(status_code=400, detail="Project has no nodes to execute.")

    # 1) Pre-flight check (non-mutating) so we can return a friendly 200+allowed:false
    #    instead of throwing — keeps the existing FE contract working.
    pre = await can_afford(db, user, "workflow_run")
    if not pre.get("allowed"):
        return pre

    # 2) Atomic debit. find_one_and_update inside credit_wallet.debit() guarantees
    #    concurrent calls cannot both pass — second caller will see ValueError and
    #    we surface it as the same allowed:false dict.
    try:
        debit_info = await debit(db, user, "workflow_run", ref=project_id)
    except ValueError:
        # Lost the race or balance dropped between can_afford() and debit().
        return await can_afford(db, user, "workflow_run")

    ctx = _build_ctx(db, user)
    # The executor expects a workflow doc with `nodes` + `edges`; bot_projects already match that shape.
    wf = {"id": project["id"], "nodes": project.get("nodes", []), "edges": project.get("edges", [])}
    result = await execute_workflow_dag(wf, ctx)
    run_id = await _log_run(db, user_id, project_id, "bot_project", result)

    return {
        "success": bool(result["success"]),
        "run_id": run_id,
        "duration_ms": result["duration_ms"],
        "output": result.get("final_output"),
        "error": result.get("error"),
        "node_results": result.get("node_results"),
        "credits": {
            "cost": debit_info.get("cost"),
            "balance": debit_info.get("balance"),
            "unlimited": debit_info.get("unlimited", False),
        },
    }

