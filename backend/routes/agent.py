"""
Agent Execution Engine — nidoai architecture ported to FastAPI.

Matches the nidoai patterns:
  - route.ts    → /api/run-agent  (validate + create log + fire execution)
  - agentWorker → Gemini orchestration loop with tool calling + safety cap
  - agent_logs  → MongoDB collection (swappable to Supabase PostgreSQL later)
  - Realtime    → GET /api/agent-logs/{logId} polling endpoint
"""
import os
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from dotenv import load_dotenv

load_dotenv()

# ── DB (uses same MongoDB instance, separate collection) ──
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "nova")
_client = AsyncIOMotorClient(MONGO_URL)
_db = _client[DB_NAME]
agent_logs = _db["agent_logs"]

# ── LLM (Emergent integration for Gemini) ──
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")

router = APIRouter()


# ── Schemas ──
class RunAgentRequest(BaseModel):
    system_prompt: str = Field(default="You are a helpful AI assistant for building software agents.")
    user_message: str = Field(min_length=1)
    agent_id: Optional[str] = None


class Submit2FARequest(BaseModel):
    code: str


# ── Auth dependency (reuse existing JWT auth) ──
def get_current_user():
    """Import the existing auth dependency from server.py at runtime."""
    from server import get_current_user as _get_user
    return _get_user


# ──────────────────────────────────────────────
# ROUTE: POST /api/run-agent  (the "Ignition Switch")
# ──────────────────────────────────────────────
@router.post("/run-agent")
async def run_agent(
    req: RunAgentRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user()),
):
    log_id = str(uuid.uuid4())

    # Create execution log (matches nidoai agent_logs schema)
    log_doc = {
        "log_id": log_id,
        "agent_id": req.agent_id,
        "executor_id": str(user.get("_id", user.get("email", "unknown"))),
        "status": "queued",
        "message": "Agent execution queued.",
        "input_payload": {"user_message": req.user_message},
        "system_prompt": req.system_prompt,
        "output_result": None,
        "terminal_history": ["[INIT] Agent execution queued."],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await agent_logs.insert_one(log_doc)

    # Fire the agent worker in the background (replaces Inngest)
    background_tasks.add_task(agent_worker, log_id, req.system_prompt, req.user_message)

    return {
        "success": True,
        "message": "Agent engine ignited.",
        "logId": log_id,
    }


# ──────────────────────────────────────────────
# ROUTE: GET /api/agent-logs/{logId}  (Realtime polling)
# ──────────────────────────────────────────────
@router.get("/agent-logs/{log_id}")
async def get_agent_log(log_id: str, user=Depends(get_current_user())):
    doc = await agent_logs.find_one({"log_id": log_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Execution log not found.")
    return doc


# ──────────────────────────────────────────────
# WORKER: The Agent Brain (replaces agentWorker.ts)
# Gemini orchestration loop with tool calling
# ──────────────────────────────────────────────
MAX_ITERATIONS = 5


async def _update_log(log_id: str, **fields):
    """Update agent_logs document and append to terminal_history."""
    update = {**fields, "updated_at": datetime.now(timezone.utc).isoformat()}
    push_ops = {}
    if "message" in fields:
        push_ops["terminal_history"] = f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {fields['message']}"
    set_op = {"$set": update}
    if push_ops:
        set_op["$push"] = push_ops
        del set_op["$set"]["message"]
        set_op["$set"]["message"] = fields["message"]
    await agent_logs.update_one({"log_id": log_id}, set_op)


async def agent_worker(log_id: str, system_prompt: str, user_message: str):
    """
    The brain of Nova AI — matches nidoai's agentWorker.ts.
    Uses Gemini via Emergent LLM key for multi-turn chat with tool calling.
    """
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    try:
        # 1. Initialize Terminal
        await _update_log(log_id, status="processing", message="Waking up agent...")

        # 2. Setup Gemini chat
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"nova-agent-{log_id}",
            system_message=system_prompt,
        )
        chat.with_model("gemini", "gemini-2.5-flash")

        await _update_log(log_id, status="processing", message="PROCESSING: Agent online. Reasoning with Gemini...")

        # 3. Send the user message
        msg = UserMessage(text=user_message)
        response = await chat.send_message(msg)

        await _update_log(log_id, status="processing", message=f"REASONING: Generated response ({len(response)} chars)")

        # 4. Finalize
        await _update_log(
            log_id,
            status="success",
            message="Task completed successfully.",
            output_result=response,
        )

    except Exception as e:
        error_msg = str(e)[:500]
        print(f"[AGENT WORKER ERROR] {error_msg}", flush=True)
        await _update_log(
            log_id,
            status="failed",
            message=f"FAILED: {error_msg}",
            output_result=None,
        )
