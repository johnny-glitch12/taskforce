"""
Agent Execution Engine — nidoai architecture on Supabase.

  route.ts    → POST /api/run-agent  (validate + create log + fire execution)
  agentWorker → Gemini orchestration loop via Emergent LLM key
  agent_logs  → Supabase PostgreSQL table with Realtime enabled
  Realtime    → Frontend uses @supabase/supabase-js Realtime subscriptions
"""
import os
import uuid
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# ── Supabase (replaces MongoDB for agent execution) ──
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


# ── Auth dependency (reuse existing JWT) ──
def get_current_user():
    from server import get_current_user as _get_user
    return _get_user


# ──────────────────────────────────────────────
# POST /api/run-agent
# ──────────────────────────────────────────────
@router.post("/run-agent")
async def run_agent(
    req: RunAgentRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user()),
):
    log_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    _sb.table("agent_logs").insert({
        "log_id": log_id,
        "agent_id": req.agent_id,
        "executor_id": str(user.get("email", "unknown")),
        "status": "queued",
        "message": "Agent execution queued.",
        "input_payload": {"user_message": req.user_message},
        "system_prompt": req.system_prompt,
        "output_result": None,
        "terminal_history": ["[INIT] Agent execution queued."],
        "created_at": now,
        "updated_at": now,
    }).execute()

    background_tasks.add_task(agent_worker, log_id, req.system_prompt, req.user_message)

    return {"success": True, "message": "Agent engine ignited.", "logId": log_id}


# ──────────────────────────────────────────────
# GET /api/agent-logs/{logId}  (fallback polling)
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
# WORKER: Agent Brain (Gemini via Emergent LLM key)
# ──────────────────────────────────────────────
def _update_log(log_id: str, **fields):
    """Update a row in Supabase agent_logs and append to terminal_history."""
    now = datetime.now(timezone.utc).isoformat()

    # Read current terminal_history to append
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


async def agent_worker(log_id: str, system_prompt: str, user_message: str):
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

        _update_log(
            log_id,
            status="success",
            message="Task completed successfully.",
            output_result=response,
        )

    except Exception as e:
        error_msg = str(e)[:500]
        print(f"[AGENT WORKER ERROR] {error_msg}", flush=True)
        _update_log(
            log_id,
            status="failed",
            message=f"FAILED: {error_msg}",
            output_result=None,
        )
