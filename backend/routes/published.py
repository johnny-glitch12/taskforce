"""
Published Agents — Save Node Coding manifests to Supabase with version control.
Provides CRUD for published agents + creator analytics.

Supabase is LAZY-initialised — the module imports cleanly even when env vars
aren't set. Endpoints return 503 when called without configuration.
"""
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

_sb = None
_sb_init_attempted = False


def get_supabase():
    global _sb, _sb_init_attempted
    if _sb is not None:
        return _sb
    if _sb_init_attempted:
        return None
    _sb_init_attempted = True
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        logger.warning("[published] Supabase not configured — published-agents endpoints disabled")
        return None
    try:
        from supabase import create_client  # noqa: WPS433
        _sb = create_client(url, key)
        return _sb
    except Exception as exc:
        logger.warning(f"[published] Supabase init failed: {exc}")
        return None


def _sb_or_503():
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="Published-agents service not configured.")
    return sb


router = APIRouter()


def get_current_user():
    from server import get_current_user as _get_user
    return _get_user


# ── Schemas ──
class PublishAgentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    manifest: dict
    trust_score: int = 0
    linter_status: str = "unknown"


class UpdateAgentRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    manifest: Optional[dict] = None
    trust_score: Optional[int] = None
    linter_status: Optional[str] = None
    status: Optional[str] = None


# ──────────────────────────────────────────────
# POST /api/agents/publish — Publish a new agent manifest
# ──────────────────────────────────────────────
@router.post("/published-agents/publish")
async def publish_agent(req: PublishAgentRequest, user=Depends(get_current_user())):
    user_id = str(user.get("id", user.get("email", "unknown")))
    agent_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "agent_id": agent_id,
        "user_id": user_id,
        "name": req.name,
        "description": req.description,
        "manifest": req.manifest,
        "version": 1,
        "version_history": [{
            "version": 1,
            "published_at": now,
            "node_count": len(req.manifest.get("nodes", [])),
            "edge_count": len(req.manifest.get("edges", [])),
        }],
        "status": "published",
        "trust_score": req.trust_score,
        "linter_status": req.linter_status,
        "execution_count": 0,
        "total_revenue": 0,
        "created_at": now,
        "updated_at": now,
    }

    result = _sb_or_503().table("published_agents").insert(doc).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to publish agent.")

    return {"success": True, "agent_id": agent_id, "version": 1, "message": "Agent published to marketplace."}


# ──────────────────────────────────────────────
# PUT /api/agents/publish/{agent_id} — Update agent (creates new version)
# ──────────────────────────────────────────────
@router.put("/published-agents/{agent_id}")
async def update_published_agent(agent_id: str, req: UpdateAgentRequest, user=Depends(get_current_user())):
    user_id = str(user.get("id", user.get("email", "unknown")))

    sb = _sb_or_503()
    existing = sb.table("published_agents").select("*").eq("agent_id", agent_id).eq("user_id", user_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Agent not found or not owned by you.")

    agent = existing.data[0]
    now = datetime.now(timezone.utc).isoformat()
    updates = {"updated_at": now}

    if req.name is not None:
        updates["name"] = req.name
    if req.description is not None:
        updates["description"] = req.description
    if req.status is not None:
        updates["status"] = req.status
    if req.trust_score is not None:
        updates["trust_score"] = req.trust_score
    if req.linter_status is not None:
        updates["linter_status"] = req.linter_status

    # If manifest changed, bump version
    new_version = agent["version"]
    if req.manifest is not None:
        new_version = agent["version"] + 1
        updates["manifest"] = req.manifest
        updates["version"] = new_version
        history = agent.get("version_history", [])
        history.append({
            "version": new_version,
            "published_at": now,
            "node_count": len(req.manifest.get("nodes", [])),
            "edge_count": len(req.manifest.get("edges", [])),
        })
        updates["version_history"] = history

    sb.table("published_agents").update(updates).eq("agent_id", agent_id).execute()

    return {"success": True, "agent_id": agent_id, "version": new_version}


# ──────────────────────────────────────────────
# GET /api/agents/published — List user's published agents
# ──────────────────────────────────────────────
@router.get("/published-agents")
async def list_published_agents(user=Depends(get_current_user())):
    user_id = str(user.get("id", user.get("email", "unknown")))
    result = _sb_or_503().table("published_agents").select("*").eq("user_id", user_id).order("updated_at", desc=True).execute()
    return {"agents": result.data or []}


# ──────────────────────────────────────────────
# GET /api/agents/published/{agent_id} — Get single published agent
# ──────────────────────────────────────────────
@router.get("/published-agents/{agent_id}")
async def get_published_agent(agent_id: str, user=Depends(get_current_user())):
    user_id = str(user.get("id", user.get("email", "unknown")))
    result = _sb_or_503().table("published_agents").select("*").eq("agent_id", agent_id).eq("user_id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return result.data[0]


# ──────────────────────────────────────────────
# DELETE /api/agents/published/{agent_id}
# ──────────────────────────────────────────────
@router.delete("/published-agents/{agent_id}")
async def delete_published_agent(agent_id: str, user=Depends(get_current_user())):
    user_id = str(user.get("id", user.get("email", "unknown")))
    sb = _sb_or_503()
    existing = sb.table("published_agents").select("agent_id").eq("agent_id", agent_id).eq("user_id", user_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Agent not found.")
    sb.table("published_agents").delete().eq("agent_id", agent_id).execute()
    return {"success": True, "message": "Agent deleted."}


# ──────────────────────────────────────────────
# GET /api/creator/analytics — Creator dashboard stats
# ──────────────────────────────────────────────
@router.get("/creator/analytics")
async def get_creator_analytics(user=Depends(get_current_user())):
    user_id = str(user.get("id", user.get("email", "unknown")))

    agents = _sb_or_503().table("published_agents").select("*").eq("user_id", user_id).execute()
    agent_list = agents.data or []

    total_agents = len(agent_list)
    published = sum(1 for a in agent_list if a.get("status") == "published")
    drafts = sum(1 for a in agent_list if a.get("status") == "draft")
    total_executions = sum(a.get("execution_count", 0) for a in agent_list)
    total_revenue = sum(float(a.get("total_revenue", 0)) for a in agent_list)
    avg_trust = round(sum(a.get("trust_score", 0) for a in agent_list) / max(total_agents, 1))
    total_versions = sum(a.get("version", 1) for a in agent_list)

    return {
        "total_agents": total_agents,
        "published": published,
        "drafts": drafts,
        "total_executions": total_executions,
        "total_revenue": total_revenue,
        "avg_trust_score": avg_trust,
        "total_versions": total_versions,
        "agents": [{
            "agent_id": a["agent_id"],
            "name": a["name"],
            "status": a["status"],
            "version": a["version"],
            "trust_score": a.get("trust_score", 0),
            "execution_count": a.get("execution_count", 0),
            "total_revenue": float(a.get("total_revenue", 0)),
            "created_at": a.get("created_at"),
            "updated_at": a.get("updated_at"),
        } for a in agent_list],
    }
