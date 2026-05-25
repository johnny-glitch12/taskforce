"""
Agent Execution Engine — nidoai architecture on Supabase.
Security layers: Semantic Firewall → Rate Limit → Concurrent Cap → Execute.
"""
import os
import uuid
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from dotenv import load_dotenv
from supabase import create_client

from lib.firewall import audit_prompt
from lib.rate_limiter import check_rate_limit, check_concurrent_cap, mark_execution_active, mark_execution_done

load_dotenv()

# ── Supabase ──
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
_sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── LLM ──
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")

router = APIRouter()


# ── Schemas ──
class RunAgentRequest(BaseModel):
    system_prompt: str = Field(default="You are a helpful AI assistant for building software agents.")
    user_message: str = Field(min_length=1)
    agent_id: Optional[str] = None


# ── Auth dependency ──
def get_current_user():
    from server import get_current_user as _get_user
    return _get_user


# ──────────────────────────────────────────────
# POST /api/run-agent
# Gate: Firewall → Rate Limit → Concurrent Cap → Execute
# ──────────────────────────────────────────────
@router.post("/run-agent")
async def run_agent(
    req: RunAgentRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user()),
):
    executor_id = str(user.get("email", "unknown"))

    # ── Gate 1: Rate Limit (5 req/min per user) ──
    rate_check = check_rate_limit(executor_id)
    if not rate_check["allowed"]:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {rate_check['retry_after']}s.",
        )

    # ── Gate 2: Concurrent Execution Cap (1 active per user) ──
    conc_check = check_concurrent_cap(_sb, executor_id)
    if not conc_check["allowed"]:
        raise HTTPException(
            status_code=409,
            detail=f"Agent already running (log: {conc_check['active_log_id'][:8]}...). Wait for it to finish.",
        )

    # Reserve the slot immediately (prevents race conditions)
    log_id = str(uuid.uuid4())
    mark_execution_active(executor_id, log_id)
    print(f"[AGENT] Slot reserved for {executor_id} -> {log_id[:8]}", flush=True)

    # ── Gate 3: Semantic Firewall (LLM prompt audit) ──
    try:
        audit = await audit_prompt(req.user_message, req.system_prompt)
        if not audit["allowed"]:
            mark_execution_done(executor_id)
            raise HTTPException(
                status_code=403,
                detail=f"Prompt blocked by security firewall. Verdict: {audit['verdict']}.",
            )
    except HTTPException:
        raise
    except Exception:
        audit = {"verdict": "SAFE", "allowed": True}

    # ── All gates passed → Execute ──
    now = datetime.now(timezone.utc).isoformat()

    _sb.table("agent_logs").insert({
        "log_id": log_id,
        "agent_id": req.agent_id,
        "executor_id": executor_id,
        "status": "queued",
        "message": "Agent execution queued.",
        "input_payload": {"user_message": req.user_message},
        "system_prompt": req.system_prompt,
        "output_result": None,
        "terminal_history": [
            "[INIT] Agent execution queued.",
            f"[FIREWALL] Prompt audited: {audit['verdict']}",
        ],
        "created_at": now,
        "updated_at": now,
    }).execute()

    background_tasks.add_task(agent_worker, log_id, req.system_prompt, req.user_message, executor_id)

    return {
        "success": True,
        "message": "Agent engine ignited.",
        "logId": log_id,
        "firewall": audit["verdict"],
    }


# ──────────────────────────────────────────────
# GET /api/agent-logs/{logId}
# ──────────────────────────────────────────────
@router.get("/agent-logs/{log_id}")
async def get_agent_log(log_id: str, user=Depends(get_current_user())):
    result = _sb.table("agent_logs").select("*").eq("log_id", log_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Execution log not found.")
    row = result.data[0]
    row.pop("id", None)
    return row


# ──────────────────────────────────────────────
# WORKER: Agent Brain
# ──────────────────────────────────────────────
def _update_log(log_id: str, **fields):
    now = datetime.now(timezone.utc).isoformat()
    current = _sb.table("agent_logs").select("terminal_history").eq("log_id", log_id).execute()
    history = current.data[0]["terminal_history"] if current.data else []
    if "message" in fields:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        history.append(f"[{ts}] {fields['message']}")
    _sb.table("agent_logs").update({
        **fields,
        "terminal_history": history,
        "updated_at": now,
    }).eq("log_id", log_id).execute()


async def agent_worker(log_id: str, system_prompt: str, user_message: str, executor_id: str):
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    try:
        _update_log(log_id, status="processing", message="Waking up agent...")

        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"nova-agent-{log_id}",
            system_message=system_prompt,
        )
        chat.with_model("gemini", "gemini-2.5-flash")

        _update_log(log_id, status="processing", message="PROCESSING: Agent online. Reasoning with Gemini...")

        msg = UserMessage(text=user_message)
        response = await chat.send_message(msg)

        _update_log(log_id, status="processing", message=f"REASONING: Generated response ({len(response)} chars)")
        _update_log(log_id, status="success", message="Task completed successfully.", output_result=response)

    except Exception as e:
        error_msg = str(e)[:500]
        print(f"[AGENT WORKER ERROR] {error_msg}", flush=True)
        _update_log(log_id, status="failed", message=f"FAILED: {error_msg}", output_result=None)
    finally:
        mark_execution_done(executor_id)
