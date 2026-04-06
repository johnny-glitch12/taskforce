from fastapi import FastAPI, APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import re
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
import secrets
from datetime import datetime, timezone, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionResponse, CheckoutStatusResponse, CheckoutSessionRequest
import subprocess
import asyncio as aio
import sys
import json
import importlib
from fastapi import BackgroundTasks

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT config
JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security
security = HTTPBearer(auto_error=False)

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Scheduler
scheduler = AsyncIOScheduler()

# ─── Models ───

class UserCreate(BaseModel):
    email: str
    password: str
    name: str = ""

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    name: str
    role: str
    client_id: Optional[str] = None
    tier: str = "free"
    created_at: str

class TokenResponse(BaseModel):
    token: str
    user: UserResponse

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class WaitlistCreate(BaseModel):
    email: str

class WaitlistResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    created_at: str

class WaitlistCountResponse(BaseModel):
    count: int

class AgentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int
    title: str
    shortTitle: str
    description: str
    longDescription: str = ""
    image: Optional[str] = None
    creator_id: str
    creator_name: str
    creator_username: str
    creator_initial: str
    creator_color: str
    creator_verified: bool = True
    rating: float
    reviews: int
    trustScore: int
    price: int
    buyPrice: int = 0
    category: str
    trending: bool = False
    trendingLabel: Optional[str] = None
    deployCount: int = 0
    setupTime: str = ""
    features: List[str] = []
    demoGreeting: str = ""

class CreatorResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    username: str
    initial: str
    color: str
    verified: bool = True
    trustScore: int
    heroStat: str
    topCategory: str
    bio: str = ""
    responseTime: str = ""
    memberSince: str = ""
    completionRate: str = ""
    agentPreviews: List[str] = []
    is_supernova: bool = False

class ReviewResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    agent_id: int
    user_name: str
    rating: int
    date: str
    text: str

# Studio models
class WorkflowNode(BaseModel):
    id: str
    type: str = "default"
    label: str = ""
    sub: str = ""
    icon: str = ""
    x: float = 0
    y: float = 0
    data: Dict[str, Any] = {}

class WorkflowEdge(BaseModel):
    source: str = Field(alias="from", default="")
    target: str = Field(alias="to", default="")

    model_config = ConfigDict(populate_by_name=True)

class WorkflowCreate(BaseModel):
    name: str = "Untitled Workflow"
    mode: str = "vibe"
    vibe_messages: List[Dict[str, str]] = []
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    code_json: str = ""

class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    mode: Optional[str] = None
    vibe_messages: Optional[List[Dict[str, str]]] = None
    nodes: Optional[List[Dict[str, Any]]] = None
    edges: Optional[List[Dict[str, Any]]] = None
    code_json: Optional[str] = None

class WorkflowResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    user_id: str
    name: str
    mode: str
    vibe_messages: List[Dict[str, str]]
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    code_json: str
    trust_score: Optional[int] = None
    linter_status: Optional[str] = None
    created_at: str
    updated_at: str

# Linter models
class LinterScanRequest(BaseModel):
    workflow_id: Optional[str] = None
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]

class LinterFlag(BaseModel):
    level: str
    node_id: str = ""
    message: str

class LinterResult(BaseModel):
    trust_score: int
    status: str
    flags: List[LinterFlag]

# Export model
class ExportResult(BaseModel):
    agent_id: int
    format: str
    workflow_json: Dict[str, Any]
    export_url: str

# ─── Auth Helpers ───

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(credentials.credentials)
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_optional_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
        return user
    except JWTError:
        return None

# ─── Auth Endpoints ───

@api_router.post("/auth/register", response_model=TokenResponse)
async def register(data: UserCreate):
    existing = await db.users.find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    user_doc = {
        "id": user_id,
        "email": data.email,
        "password_hash": hash_password(data.password),
        "name": data.name or data.email.split("@")[0],
        "role": "user",
        "created_at": now,
    }
    await db.users.insert_one(user_doc)
    token = create_token(user_id, data.email, "user")
    return TokenResponse(
        token=token,
        user=UserResponse(id=user_id, email=data.email, name=user_doc["name"], role="user", created_at=now)
    )

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(data: UserLogin):
    user = await db.users.find_one({"email": data.email}, {"_id": 0})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token(user["id"], user["email"], user["role"])
    return TokenResponse(
        token=token,
        user=UserResponse(id=user["id"], email=user["email"], name=user["name"], role=user["role"], client_id=user.get("client_id"), tier=user.get("tier", "free"), created_at=user["created_at"])
    )

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(user=Depends(get_current_user)):
    return UserResponse(id=user["id"], email=user["email"], name=user["name"], role=user["role"], client_id=user.get("client_id"), tier=user.get("tier", "free"), created_at=user["created_at"])

# ─── Password Reset Endpoints ───

@api_router.post("/auth/forgot-password")
async def forgot_password(data: ForgotPasswordRequest):
    user = await db.users.find_one({"email": data.email}, {"_id": 0})
    if not user:
        # Return success even if email not found (prevent enumeration)
        return {"message": "If that email exists, a reset link has been generated.", "reset_token": None}
    reset_token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    await db.password_resets.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "email": data.email,
        "token": reset_token,
        "expires_at": expires.isoformat(),
        "used": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    # In production, send email with reset link. For demo, return the token.
    logger.info(f"Password reset token generated for {data.email}: {reset_token}")
    return {"message": "If that email exists, a reset link has been generated.", "reset_token": reset_token}

@api_router.post("/auth/reset-password")
async def reset_password(data: ResetPasswordRequest):
    reset_entry = await db.password_resets.find_one({"token": data.token, "used": False}, {"_id": 0})
    if not reset_entry:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    expires = datetime.fromisoformat(reset_entry["expires_at"])
    if datetime.now(timezone.utc) > expires:
        raise HTTPException(status_code=400, detail="Reset token has expired")
    new_hash = hash_password(data.new_password)
    await db.users.update_one({"id": reset_entry["user_id"]}, {"$set": {"password_hash": new_hash}})
    await db.password_resets.update_one({"token": data.token}, {"$set": {"used": True}})
    return {"message": "Password reset successfully. You can now log in with your new password."}

# ─── Waitlist Endpoints ───

@api_router.post("/waitlist", response_model=WaitlistResponse)
async def join_waitlist(data: WaitlistCreate):
    existing = await db.waitlist.find_one({"email": data.email})
    if existing:
        return WaitlistResponse(id=existing["id"], email=existing["email"], created_at=existing["created_at"])
    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {"id": entry_id, "email": data.email, "created_at": now}
    await db.waitlist.insert_one(doc)
    logger.info(f"New waitlist signup: {data.email}")
    return WaitlistResponse(id=entry_id, email=data.email, created_at=now)

@api_router.get("/waitlist/count", response_model=WaitlistCountResponse)
async def get_waitlist_count():
    count = await db.waitlist.count_documents({})
    return WaitlistCountResponse(count=count)

@api_router.get("/waitlist", response_model=List[WaitlistResponse])
async def get_waitlist(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    entries = await db.waitlist.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return entries

# ─── Agent Endpoints ───

@api_router.get("/agents", response_model=List[AgentResponse])
async def get_agents(search: str = "", category: str = "all"):
    query = {}
    if category and category != "all":
        query["category"] = category
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"shortTitle": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
        ]
    agents = await db.agents.find(query, {"_id": 0}).sort("deployCount", -1).to_list(100)
    return agents

@api_router.get("/agents/search")
async def search_agents(
    q: str = Query("", description="Search term"),
    category: str = Query("all"),
    min_trust: int = Query(0, ge=0, le=100),
    sort_by: str = Query("trending"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    match_stage: Dict[str, Any] = {}
    if q:
        match_stage["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"shortTitle": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
        ]
    if category and category != "all":
        match_stage["category"] = category
    if min_trust > 0:
        match_stage["trustScore"] = {"$gte": min_trust}

    sort_map = {
        "trending": ("deployCount", -1),
        "price_asc": ("price", 1),
        "price_desc": ("price", -1),
        "newest": ("id", -1),
        "rating": ("rating", -1),
        "trust": ("trustScore", -1),
    }
    sort_field, sort_dir = sort_map.get(sort_by, ("deployCount", -1))

    pipeline = [
        {"$match": match_stage} if match_stage else {"$match": {}},
        {"$lookup": {
            "from": "creators",
            "localField": "creator_id",
            "foreignField": "id",
            "as": "creator_info"
        }},
        {"$addFields": {
            "creator_supernova": {
                "$cond": {
                    "if": {"$gt": [{"$size": "$creator_info"}, 0]},
                    "then": {"$arrayElemAt": ["$creator_info.is_supernova", 0]},
                    "else": False
                }
            }
        }},
        {"$project": {"_id": 0, "creator_info": 0}},
        {"$sort": {sort_field: sort_dir}},
        {"$skip": offset},
        {"$limit": limit},
    ]

    agents = await db.agents.aggregate(pipeline).to_list(length=limit)
    total = await db.agents.count_documents(match_stage if match_stage else {})

    return {
        "agents": agents,
        "total": total,
        "offset": offset,
        "limit": limit,
    }

@api_router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: int):
    agent = await db.agents.find_one({"id": agent_id}, {"_id": 0})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@api_router.get("/agents/{agent_id}/reviews", response_model=List[ReviewResponse])
async def get_agent_reviews(agent_id: int):
    reviews = await db.reviews.find({"agent_id": agent_id}, {"_id": 0}).sort("date", -1).to_list(100)
    return reviews

@api_router.post("/agents/{agent_id}/export")
async def export_agent(agent_id: int, user=Depends(get_current_user)):
    agent = await db.agents.find_one({"id": agent_id}, {"_id": 0})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    workflow = {
        "agent": agent["shortTitle"].lower().replace(" ", "-"),
        "version": "1.0.0",
        "metadata": {
            "name": agent["shortTitle"],
            "description": agent["description"],
            "category": agent["category"],
            "trust_score": agent["trustScore"],
        },
        "nodes": [
            {"id": "trigger_001", "type": "trigger", "config": {"source": "api", "method": "POST"}},
            {"id": "llm_001", "type": "llm", "config": {"model": "nova-7b", "task": "process", "temperature": 0.3}},
            {"id": "action_001", "type": "action", "config": {"type": "respond", "format": "json"}},
        ],
        "edges": [
            {"from": "trigger_001", "to": "llm_001"},
            {"from": "llm_001", "to": "action_001"},
        ],
    }
    return ExportResult(
        agent_id=agent_id,
        format="nova_workflow_v1",
        workflow_json=workflow,
        export_url=f"/exports/{agent['shortTitle'].lower().replace(' ', '-')}.json"
    )

# ─── Creator Endpoints ───

@api_router.get("/creators", response_model=List[CreatorResponse])
async def get_creators():
    creators = await db.creators.find({}, {"_id": 0}).to_list(100)
    return creators

@api_router.get("/creators/{creator_id}")
async def get_creator(creator_id: str):
    creator = await db.creators.find_one({"id": creator_id}, {"_id": 0})
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")
    agents = await db.agents.find({"creator_id": creator_id}, {"_id": 0}).to_list(100)
    return {"creator": creator, "agents": agents}

# ─── Studio Workflow Endpoints ───

@api_router.post("/studio/workflows", response_model=WorkflowResponse)
async def create_workflow(data: WorkflowCreate, user=Depends(get_current_user)):
    workflow_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": workflow_id,
        "user_id": user["id"],
        "name": data.name,
        "mode": data.mode,
        "vibe_messages": data.vibe_messages,
        "nodes": data.nodes,
        "edges": data.edges,
        "code_json": data.code_json,
        "trust_score": None,
        "linter_status": None,
        "created_at": now,
        "updated_at": now,
    }
    await db.workflows.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.get("/studio/workflows", response_model=List[WorkflowResponse])
async def list_workflows(user=Depends(get_current_user)):
    workflows = await db.workflows.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("updated_at", -1).to_list(100)
    return workflows

@api_router.get("/studio/workflows/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str, user=Depends(get_current_user)):
    wf = await db.workflows.find_one({"id": workflow_id, "user_id": user["id"]}, {"_id": 0})
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf

@api_router.put("/studio/workflows/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(workflow_id: str, data: WorkflowUpdate, user=Depends(get_current_user)):
    wf = await db.workflows.find_one({"id": workflow_id, "user_id": user["id"]})
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}
    for field in ["name", "mode", "vibe_messages", "nodes", "edges", "code_json"]:
        val = getattr(data, field, None)
        if val is not None:
            update_fields[field] = val
    await db.workflows.update_one({"id": workflow_id}, {"$set": update_fields})
    updated = await db.workflows.find_one({"id": workflow_id}, {"_id": 0})
    return updated

@api_router.delete("/studio/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str, user=Depends(get_current_user)):
    result = await db.workflows.delete_one({"id": workflow_id, "user_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"message": "Workflow deleted"}

# ─── Compliance Linter Engine ───

BLACKLISTED_DOMAINS = [
    "evil.com", "malware.net", "phishing.io", "hack3r.org",
    "darkweb.xyz", "exploit.cc", "trojan.site",
]

PII_PATTERNS = [
    r"\bssn\b", r"\bsocial.?security\b", r"\bcredit.?card\b",
    r"\bpassword\b", r"\bsecret\b", r"\bapi.?key\b",
    r"\bprivate.?key\b", r"\baccess.?token\b",
]

PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(previous|above|all)\s+instructions",
    r"you\s+are\s+now\s+",
    r"reveal\s+(your|the)\s+(system|hidden|secret)",
    r"output\s+(your|the)\s+(prompt|instructions)",
    r"disregard\s+(all|any)\s+",
]

@api_router.post("/linter/scan", response_model=LinterResult)
async def scan_workflow(data: LinterScanRequest):
    score = 100
    flags: List[LinterFlag] = []

    for node in data.nodes:
        node_id = node.get("id", "unknown")
        node_data = node.get("data", {})
        node_type = node.get("type", "")

        # Rule 1: Exposed API keys / secrets in node data
        data_str = str(node_data).lower()
        for pattern in PII_PATTERNS:
            if re.search(pattern, data_str, re.IGNORECASE):
                score -= 20
                flags.append(LinterFlag(
                    level="critical",
                    node_id=node_id,
                    message=f"Potential sensitive data detected in node '{node_id}'. Matched pattern: {pattern}"
                ))
                break

        # Rule 2: Check for plaintext API keys in config
        for key, val in node_data.items():
            if isinstance(val, str) and ("api_key" in key.lower() or "secret" in key.lower() or "token" in key.lower()):
                if val and not val.startswith("${{"):
                    score -= 25
                    flags.append(LinterFlag(
                        level="critical",
                        node_id=node_id,
                        message=f"Raw credential '{key}' exposed in node '{node_id}'. Use environment variable references (${{{{VAR_NAME}}}})."
                    ))

        # Rule 3: Unverified external URLs
        url = node_data.get("url", "") or node_data.get("endpoint", "")
        if url:
            if url.startswith("http://") and "localhost" not in url:
                score -= 10
                flags.append(LinterFlag(
                    level="warning",
                    node_id=node_id,
                    message=f"Unencrypted HTTP endpoint in node '{node_id}'. Use HTTPS for security."
                ))
            for domain in BLACKLISTED_DOMAINS:
                if domain in url:
                    score -= 30
                    flags.append(LinterFlag(
                        level="critical",
                        node_id=node_id,
                        message=f"Blacklisted domain '{domain}' detected in node '{node_id}'."
                    ))

        # Rule 4: Prompt injection analysis for LLM nodes
        if node_type in ["llm", "prompt", "ai"]:
            prompt_text = node_data.get("system_prompt", "") or node_data.get("prompt", "") or node_data.get("instructions", "")
            if prompt_text:
                for injection_pattern in PROMPT_INJECTION_PATTERNS:
                    if re.search(injection_pattern, prompt_text, re.IGNORECASE):
                        score -= 15
                        flags.append(LinterFlag(
                            level="warning",
                            node_id=node_id,
                            message=f"Potential prompt injection vulnerability in node '{node_id}'. Suspicious instruction pattern detected."
                        ))
                        break

        # Rule 5: PII transmission without encryption
        if node_type in ["http_request", "webhook", "api_call"]:
            transmits_pii = any(
                re.search(p, str(node_data), re.IGNORECASE) for p in PII_PATTERNS[:4]
            )
            if transmits_pii and not url.startswith("https://"):
                score -= 20
                flags.append(LinterFlag(
                    level="critical",
                    node_id=node_id,
                    message=f"Node '{node_id}' transmits potential PII over unencrypted connection."
                ))

    # Rule 6: Orphan nodes (nodes not connected by any edge)
    all_node_ids = {n.get("id") for n in data.nodes}
    connected_nodes = set()
    for edge in data.edges:
        connected_nodes.add(edge.get("from", edge.get("source", "")))
        connected_nodes.add(edge.get("to", edge.get("target", "")))
    orphans = all_node_ids - connected_nodes
    if orphans and len(data.nodes) > 1:
        score -= 5
        for orphan_id in orphans:
            flags.append(LinterFlag(
                level="info",
                node_id=orphan_id,
                message=f"Node '{orphan_id}' is not connected to any edge. It will not execute."
            ))

    score = max(0, min(100, score))
    status = "certified" if score >= 85 else "flagged" if score >= 50 else "rejected"

    # If linked to a workflow, update its trust score
    if data.workflow_id:
        await db.workflows.update_one(
            {"id": data.workflow_id},
            {"$set": {"trust_score": score, "linter_status": status}}
        )

    return LinterResult(trust_score=score, status=status, flags=flags)

# ─── Supernova Engine ───

async def evaluate_supernovas():
    logger.info("Running Supernova Evaluation Engine...")
    creators = await db.creators.find({}, {"_id": 0}).to_list(100)
    for creator in creators:
        creator_agents = await db.agents.find({"creator_id": creator["id"]}, {"_id": 0}).to_list(100)
        if not creator_agents:
            continue
        total_deploys = sum(a.get("deployCount", 0) for a in creator_agents)
        avg_rating = sum(a.get("rating", 0) for a in creator_agents) / len(creator_agents)
        avg_trust = sum(a.get("trustScore", 0) for a in creator_agents) / len(creator_agents)
        total_reviews = sum(a.get("reviews", 0) for a in creator_agents)

        is_supernova = (
            total_deploys >= 500
            and avg_rating >= 4.7
            and avg_trust >= 90
            and total_reviews >= 50
        )
        await db.creators.update_one(
            {"id": creator["id"]},
            {"$set": {"is_supernova": is_supernova}}
        )
    logger.info("Supernova evaluation complete.")

# ─── Seed Endpoint ───

@api_router.post("/seed")
async def seed_database():
    count = await db.agents.count_documents({})
    if count > 0:
        return {"message": "Database already seeded", "agents": count}

    # Seed admin user
    admin_exists = await db.users.find_one({"email": "admin@nova.ai"})
    if not admin_exists:
        admin_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await db.users.insert_one({
            "id": admin_id, "email": "admin@nova.ai",
            "password_hash": hash_password("admin123"),
            "name": "Nova Admin", "role": "admin", "created_at": now,
        })
        logger.info("Admin user seeded: admin@nova.ai / admin123")

    # Seed creators
    creators_data = [
        {"id": "datawiz", "name": "Sarah Chen", "username": "@DataWiz", "initial": "S", "color": "#8B5CF6", "verified": True, "trustScore": 99, "heroStat": "1.2k+ Agents Deployed", "topCategory": "Top Rated in Data", "bio": "Former data scientist at Stripe. Building the future of automated analytics.", "responseTime": "< 1 hour", "memberSince": "Jan 2025", "completionRate": "99%", "agentPreviews": ["Data Analyst", "ETL Pipeline", "Anomaly Detector"], "is_supernova": False},
        {"id": "salesforge", "name": "Marcus Rivera", "username": "@SalesForge", "initial": "M", "color": "#6D28D9", "verified": True, "trustScore": 97, "heroStat": "890+ Agents Deployed", "topCategory": "Top Rated in Sales", "bio": "Ex-VP Sales at HubSpot. Automating the entire outbound pipeline.", "responseTime": "< 2 hours", "memberSince": "Mar 2025", "completionRate": "98%", "agentPreviews": ["Sales Dev Rep", "Lead Qualifier", "Outbound Pro"], "is_supernova": False},
        {"id": "cxmaster", "name": "Priya Sharma", "username": "@CXMaster", "initial": "P", "color": "#7C3AED", "verified": True, "trustScore": 98, "heroStat": "1.5k+ Agents Deployed", "topCategory": "#1 in Support", "bio": "Built CX teams at Zendesk and Intercom. Now building agents that scale empathy.", "responseTime": "< 30 min", "memberSince": "Dec 2024", "completionRate": "100%", "agentPreviews": ["Customer Service Pro", "Ticket Triage", "CSAT Analyst"], "is_supernova": False},
        {"id": "codepilot", "name": "Alex Dubois", "username": "@CodePilot", "initial": "A", "color": "#A78BFA", "verified": True, "trustScore": 96, "heroStat": "640+ Agents Deployed", "topCategory": "Top Rated in Coding", "bio": "Staff engineer turned agent builder. Making code reviews 10x faster.", "responseTime": "< 3 hours", "memberSince": "Feb 2025", "completionRate": "97%", "agentPreviews": ["Code Reviewer", "CI/CD Agent", "Bug Triager"], "is_supernova": False},
        {"id": "financeai", "name": "James Okonkwo", "username": "@FinanceAI", "initial": "J", "color": "#5B21B6", "verified": True, "trustScore": 99, "heroStat": "720+ Agents Deployed", "topCategory": "#1 in Finance", "bio": "CPA + ML engineer. Building enterprise-grade compliance automation.", "responseTime": "< 1 hour", "memberSince": "Nov 2024", "completionRate": "100%", "agentPreviews": ["Finance Auditor", "Expense Tracker", "Risk Scorer"], "is_supernova": False},
    ]
    await db.creators.insert_many(creators_data)

    # Seed agents
    agents_data = [
        {"id": 1, "title": "I will deploy a Customer Service Pro agent trained on your docs", "shortTitle": "Customer Service Pro", "description": "Handles tickets, resolves issues, escalates edge cases with empathy.", "longDescription": "This AI agent integrates with your existing helpdesk (Zendesk, Intercom, Freshdesk) and learns from your documentation, FAQs, and past ticket resolutions. It handles L1 support autonomously and intelligently escalates complex issues to human agents with full context.", "image": "https://images.unsplash.com/photo-1744324480866-1794a1bf193c?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA0MTJ8MHwxfHNlYXJjaHwzfHxmdXR1cmlzdGljJTIwYWklMjBicmFpbiUyMGRhcmt8ZW58MHx8fHwxNzc0NDg1NjE4fDA&ixlib=rb-4.1.0&q=85", "creator_id": "cxmaster", "creator_name": "Priya Sharma", "creator_username": "@CXMaster", "creator_initial": "P", "creator_color": "#7C3AED", "creator_verified": True, "rating": 4.9, "reviews": 124, "trustScore": 98, "price": 49, "buyPrice": 499, "category": "support", "trending": True, "trendingLabel": "#1 in Support", "deployCount": 847, "setupTime": "< 15 min", "features": ["Multi-language support", "Sentiment detection", "Auto-escalation", "Custom training on your docs", "Zendesk/Intercom integration"], "demoGreeting": "Hi! I'm the Customer Service Pro agent. Ask me anything about handling refunds, tracking orders, or resolving support tickets."},
        {"id": 2, "title": "I will build an AI Sales Dev Rep that books meetings on autopilot", "shortTitle": "Sales Dev Rep", "description": "Qualifies leads, personalizes outreach, and books meetings automatically.", "longDescription": "Your AI-powered SDR that never sleeps. This agent monitors your inbound leads, researches prospects, crafts hyper-personalized outreach sequences, and handles the back-and-forth to book qualified meetings directly on your calendar.", "image": "https://images.pexels.com/photos/5181148/pexels-photo-5181148.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940", "creator_id": "salesforge", "creator_name": "Marcus Rivera", "creator_username": "@SalesForge", "creator_initial": "M", "creator_color": "#6D28D9", "creator_verified": True, "rating": 4.8, "reviews": 89, "trustScore": 96, "price": 79, "buyPrice": 799, "category": "sales", "trending": True, "trendingLabel": "#1 in Sales", "deployCount": 612, "setupTime": "< 30 min", "features": ["LinkedIn prospect research", "Email personalization", "Meeting scheduling", "CRM auto-sync", "A/B sequence testing"], "demoGreeting": "Hey! I'm your Sales Dev Rep agent. I can help you qualify leads, write outreach emails, and book meetings. Try me!"},
        {"id": 3, "title": "I will create a Data Analyst agent for automated reporting", "shortTitle": "Data Analyst", "description": "Turns raw datasets into insights with anomaly detection and trend analysis.", "longDescription": "Upload your data or connect your database, and this agent generates automated reports, detects anomalies in real-time, identifies trends, and delivers actionable recommendations.", "image": "https://images.unsplash.com/photo-1697899001862-59699946ea29?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2ODh8MHwxfHNlYXJjaHwxfHxhYnN0cmFjdCUyMDNkJTIwZ2VvbWV0cmljJTIwc2hhcGUlMjBkYXJrJTIwYmFja2dyb3VuZHxlbnwwfHx8fDE3NzQ0ODU2MTR8MA&ixlib=rb-4.1.0&q=85", "creator_id": "datawiz", "creator_name": "Sarah Chen", "creator_username": "@DataWiz", "creator_initial": "S", "creator_color": "#8B5CF6", "creator_verified": True, "rating": 4.9, "reviews": 201, "trustScore": 99, "price": 99, "buyPrice": 999, "category": "data", "trending": True, "trendingLabel": "Trending", "deployCount": 1034, "setupTime": "< 20 min", "features": ["SQL database connection", "Anomaly detection", "Trend forecasting", "Slack/email reports", "Natural language queries"], "demoGreeting": "Hello! I'm the Data Analyst agent. Ask me to analyze trends, detect anomalies, or generate reports from your data."},
        {"id": 4, "title": "I will deploy an AI Code Reviewer for your pull requests", "shortTitle": "Code Reviewer", "description": "Reviews PRs, catches bugs, suggests improvements, enforces standards.", "longDescription": "Plugs into your GitHub/GitLab workflow and reviews every pull request automatically. It catches bugs, security vulnerabilities, performance issues, and style violations.", "image": None, "creator_id": "codepilot", "creator_name": "Alex Dubois", "creator_username": "@CodePilot", "creator_initial": "A", "creator_color": "#A78BFA", "creator_verified": True, "rating": 4.7, "reviews": 67, "trustScore": 95, "price": 59, "buyPrice": 599, "category": "coding", "trending": False, "trendingLabel": None, "deployCount": 389, "setupTime": "< 10 min", "features": ["GitHub/GitLab integration", "Security scanning", "Performance analysis", "Style enforcement", "Inline PR comments"], "demoGreeting": "Hi! I'm the Code Reviewer agent. Paste a code snippet and I'll review it for bugs, security issues, and best practices."},
        {"id": 5, "title": "I will build a Finance Auditor agent for compliance checks", "shortTitle": "Finance Auditor", "description": "Automates audit trails, flags anomalies, ensures regulatory compliance.", "longDescription": "Enterprise-grade compliance automation. This agent continuously monitors financial transactions, flags suspicious patterns, generates audit trails, and ensures SOX/GAAP compliance.", "image": None, "creator_id": "financeai", "creator_name": "James Okonkwo", "creator_username": "@FinanceAI", "creator_initial": "J", "creator_color": "#5B21B6", "creator_verified": True, "rating": 4.9, "reviews": 156, "trustScore": 99, "price": 129, "buyPrice": 1299, "category": "finance", "trending": True, "trendingLabel": "#1 in Finance", "deployCount": 523, "setupTime": "< 45 min", "features": ["SOX/GAAP compliance", "Anomaly flagging", "Audit trail generation", "QuickBooks integration", "Real-time monitoring"], "demoGreeting": "Hello! I'm the Finance Auditor agent. Ask me about compliance checks, audit procedures, or transaction monitoring."},
        {"id": 6, "title": "I will create a Lead Qualifier agent that scores and routes leads", "shortTitle": "Lead Qualifier", "description": "Scores inbound leads by intent, routes hot leads to reps instantly.", "longDescription": "This agent scores every inbound lead in real-time based on firmographic data, behavioral signals, and intent indicators. Hot leads are instantly routed to available reps.", "image": None, "creator_id": "salesforge", "creator_name": "Marcus Rivera", "creator_username": "@SalesForge", "creator_initial": "M", "creator_color": "#6D28D9", "creator_verified": True, "rating": 4.8, "reviews": 112, "trustScore": 97, "price": 69, "buyPrice": 699, "category": "sales", "trending": False, "trendingLabel": None, "deployCount": 445, "setupTime": "< 25 min", "features": ["Real-time lead scoring", "Intent signal detection", "Slack/email routing", "CRM enrichment", "Nurture automation"], "demoGreeting": "Hey! I'm the Lead Qualifier agent. Tell me about a lead and I'll score and qualify them for you."},
    ]
    await db.agents.insert_many(agents_data)

    # Seed reviews
    reviews_data = []
    review_templates = [
        {"user_name": "Emily T.", "rating": 5, "date": "2 weeks ago", "text": "Absolutely game-changing. Set it up in 10 minutes and it resolved 60% of our tickets in the first week."},
        {"user_name": "David K.", "rating": 5, "date": "1 month ago", "text": "We replaced 3 part-time contractors with this agent. ROI was immediate. The logic is perfect."},
        {"user_name": "Sarah M.", "rating": 4, "date": "1 month ago", "text": "Great agent overall. Took a bit of tweaking but once dialed in, it's incredibly consistent."},
        {"user_name": "James R.", "rating": 5, "date": "3 weeks ago", "text": "Best investment we've made this quarter. Our metrics improved 15% within a month of deployment."},
    ]
    for agent in agents_data:
        for tmpl in review_templates:
            reviews_data.append({
                "id": str(uuid.uuid4()),
                "agent_id": agent["id"],
                "user_name": tmpl["user_name"],
                "rating": tmpl["rating"],
                "date": tmpl["date"],
                "text": tmpl["text"],
            })
    await db.reviews.insert_many(reviews_data)

    # Seed waitlist entries for social proof
    waitlist_seed = [
        {"id": str(uuid.uuid4()), "email": "early@adopter.com", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "email": "beta@tester.io", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "email": "founder@startup.ai", "created_at": datetime.now(timezone.utc).isoformat()},
    ]
    await db.waitlist.insert_many(waitlist_seed)

    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.waitlist.create_index("email", unique=True)
    await db.agents.create_index("id", unique=True)
    await db.agents.create_index("category")
    await db.agents.create_index([("title", "text"), ("shortTitle", "text"), ("description", "text")])
    await db.creators.create_index("id", unique=True)
    await db.reviews.create_index("agent_id")
    await db.workflows.create_index("user_id")
    await db.workflows.create_index("id", unique=True)
    await db.password_resets.create_index("token", unique=True)
    await db.user_agents.create_index("user_id")
    await db.user_agents.create_index("id", unique=True)
    await db.user_agents.create_index("webhook_key", unique=True)
    await db.agent_executions.create_index("agent_id")
    await db.agent_executions.create_index("user_id")
    await db.payment_transactions.create_index("session_id")

    # Run initial supernova evaluation
    await evaluate_supernovas()

    logger.info("Database seeded successfully")
    return {"message": "Database seeded", "agents": len(agents_data), "creators": len(creators_data), "reviews": len(reviews_data)}

# ─── Dashboard & Custom Agent Models ───

AGENT_TIER_LIMITS = {"free": 3, "pro": 999999}

class UserAgentCreate(BaseModel):
    name: str
    description: str = ""
    code: str
    env_vars: Dict[str, str] = {}
    trigger_type: str = "manual"  # "manual", "webhook", "both"

class UserAgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    code: Optional[str] = None
    env_vars: Optional[Dict[str, str]] = None
    trigger_type: Optional[str] = None
    status: Optional[str] = None

class UserAgentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    user_id: str
    name: str
    description: str
    code: str
    env_vars: Dict[str, str]
    trigger_type: str
    webhook_key: str
    status: str
    last_run: Optional[str] = None
    last_result: Optional[str] = None
    run_count: int
    created_at: str
    updated_at: str

class AgentRunRequest(BaseModel):
    input_data: Any = {}

class AgentExecutionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    agent_id: str
    trigger: str
    input_data: Any
    output: str
    result: Any
    logs: str
    error: Optional[str]
    success: bool
    duration_ms: int
    created_at: str

# ─── Dashboard Endpoints ───

@api_router.get("/dashboard/stats")
async def get_dashboard_stats(user=Depends(get_current_user)):
    agent_count = await db.user_agents.count_documents({"user_id": user["id"]})
    tier = user.get("tier", "free")
    limit = AGENT_TIER_LIMITS.get(tier, 3)
    total_runs = await db.agent_executions.count_documents({"user_id": user["id"]})

    # Purchased agents
    purchased = await db.payment_transactions.count_documents({
        "user_id": user["id"], "payment_status": "paid"
    })

    return {
        "agent_count": agent_count,
        "agent_limit": limit,
        "tier": tier,
        "total_runs": total_runs,
        "purchased_agents": purchased,
    }

@api_router.get("/dashboard/purchased")
async def get_purchased_agents(user=Depends(get_current_user)):
    txns = await db.payment_transactions.find(
        {"user_id": user["id"], "payment_status": "paid"}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return txns

@api_router.get("/dashboard/agents", response_model=List[UserAgentResponse])
async def list_user_agents(user=Depends(get_current_user)):
    agents = await db.user_agents.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("updated_at", -1).to_list(100)
    return agents

@api_router.post("/dashboard/agents", response_model=UserAgentResponse)
async def create_user_agent(data: UserAgentCreate, user=Depends(get_current_user)):
    tier = user.get("tier", "free")
    limit = AGENT_TIER_LIMITS.get(tier, 3)
    count = await db.user_agents.count_documents({"user_id": user["id"]})
    if count >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"Agent limit reached ({count}/{limit}). Upgrade to Pro for unlimited agents."
        )

    # Validate code with sandbox
    from sandbox import validate_code
    err = validate_code(data.code)
    if err:
        raise HTTPException(status_code=400, detail=f"Code validation failed: {err}")

    agent_id = str(uuid.uuid4())
    webhook_key = secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": agent_id,
        "user_id": user["id"],
        "name": data.name,
        "description": data.description,
        "code": data.code,
        "env_vars": data.env_vars,
        "trigger_type": data.trigger_type,
        "webhook_key": webhook_key,
        "status": "ready",
        "last_run": None,
        "last_result": None,
        "run_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    await db.user_agents.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.get("/dashboard/agents/{agent_id}", response_model=UserAgentResponse)
async def get_user_agent(agent_id: str, user=Depends(get_current_user)):
    agent = await db.user_agents.find_one(
        {"id": agent_id, "user_id": user["id"]}, {"_id": 0}
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@api_router.put("/dashboard/agents/{agent_id}", response_model=UserAgentResponse)
async def update_user_agent(agent_id: str, data: UserAgentUpdate, user=Depends(get_current_user)):
    agent = await db.user_agents.find_one({"id": agent_id, "user_id": user["id"]})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}

    if data.code is not None:
        from sandbox import validate_code
        err = validate_code(data.code)
        if err:
            raise HTTPException(status_code=400, detail=f"Code validation failed: {err}")
        update_fields["code"] = data.code

    for field in ["name", "description", "env_vars", "trigger_type", "status"]:
        val = getattr(data, field, None)
        if val is not None:
            update_fields[field] = val

    await db.user_agents.update_one({"id": agent_id}, {"$set": update_fields})
    updated = await db.user_agents.find_one({"id": agent_id}, {"_id": 0})
    return updated

@api_router.delete("/dashboard/agents/{agent_id}")
async def delete_user_agent(agent_id: str, user=Depends(get_current_user)):
    result = await db.user_agents.delete_one({"id": agent_id, "user_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Agent not found")
    # Clean up executions
    await db.agent_executions.delete_many({"agent_id": agent_id})
    return {"message": "Agent deleted"}

@api_router.post("/dashboard/agents/{agent_id}/run", response_model=AgentExecutionResponse)
async def run_user_agent(agent_id: str, data: AgentRunRequest, user=Depends(get_current_user)):
    agent = await db.user_agents.find_one(
        {"id": agent_id, "user_id": user["id"]}, {"_id": 0}
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent["status"] == "disabled":
        raise HTTPException(status_code=400, detail="Agent is disabled")

    from sandbox import execute_code
    result = execute_code(
        code=agent["code"],
        env_vars=agent["env_vars"],
        input_data=data.input_data,
    )

    exec_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    exec_doc = {
        "id": exec_id,
        "agent_id": agent_id,
        "user_id": user["id"],
        "trigger": "manual",
        "input_data": data.input_data,
        "output": result["output"],
        "result": result["result"],
        "logs": result["logs"],
        "error": result["error"],
        "success": result["success"],
        "duration_ms": result["duration_ms"],
        "created_at": now,
    }
    await db.agent_executions.insert_one(exec_doc)
    exec_doc.pop("_id", None)

    # Update agent stats
    await db.user_agents.update_one({"id": agent_id}, {"$set": {
        "last_run": now,
        "last_result": "success" if result["success"] else "error",
        "updated_at": now,
    }, "$inc": {"run_count": 1}})

    return exec_doc

@api_router.get("/dashboard/agents/{agent_id}/executions", response_model=List[AgentExecutionResponse])
async def get_agent_executions(agent_id: str, user=Depends(get_current_user), limit: int = 20):
    agent = await db.user_agents.find_one(
        {"id": agent_id, "user_id": user["id"]}, {"_id": 0}
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    execs = await db.agent_executions.find(
        {"agent_id": agent_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(limit)
    return execs

@api_router.post("/dashboard/agents/{agent_id}/stop")
async def stop_user_agent(agent_id: str, user=Depends(get_current_user)):
    result = await db.user_agents.update_one(
        {"id": agent_id, "user_id": user["id"]},
        {"$set": {"status": "disabled", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"message": "Agent disabled"}

@api_router.post("/dashboard/agents/{agent_id}/start")
async def start_user_agent(agent_id: str, user=Depends(get_current_user)):
    result = await db.user_agents.update_one(
        {"id": agent_id, "user_id": user["id"]},
        {"$set": {"status": "ready", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"message": "Agent enabled"}

# ─── Public Webhook Trigger ───

@api_router.post("/webhook/agent/{webhook_key}")
async def webhook_trigger_agent(webhook_key: str, request: Request):
    agent = await db.user_agents.find_one({"webhook_key": webhook_key}, {"_id": 0})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent["status"] == "disabled":
        raise HTTPException(status_code=400, detail="Agent is disabled")
    if agent["trigger_type"] not in ("webhook", "both"):
        raise HTTPException(status_code=400, detail="Webhook trigger not enabled for this agent")

    try:
        body = await request.json()
    except Exception:
        body = {}

    from sandbox import execute_code
    result = execute_code(
        code=agent["code"],
        env_vars=agent["env_vars"],
        input_data=body,
    )

    exec_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    exec_doc = {
        "id": exec_id,
        "agent_id": agent["id"],
        "user_id": agent["user_id"],
        "trigger": "webhook",
        "input_data": body,
        "output": result["output"],
        "result": result["result"],
        "logs": result["logs"],
        "error": result["error"],
        "success": result["success"],
        "duration_ms": result["duration_ms"],
        "created_at": now,
    }
    await db.agent_executions.insert_one(exec_doc)

    await db.user_agents.update_one({"id": agent["id"]}, {"$set": {
        "last_run": now,
        "last_result": "success" if result["success"] else "error",
        "updated_at": now,
    }, "$inc": {"run_count": 1}})

    return {
        "success": result["success"],
        "result": result["result"],
        "output": result["output"],
        "error": result["error"],
        "duration_ms": result["duration_ms"],
    }

# ─── CSDROP Client Portal ───

CSDROP_CLIENT_ID = "csdrop"
CSDROP_BOT_DIR = Path(__file__).parent / "clients" / "csdrop"
CSDROP_LOG_DIR = CSDROP_BOT_DIR / "logs"
CSDROP_LOG_DIR.mkdir(exist_ok=True)
CSDROP_LOG_FILE = CSDROP_LOG_DIR / "current_run.log"

# Global reference to running bot process
_csdrop_bot_process = None
_csdrop_bot_logs = []
_repair_status = {"running": False, "last_result": None, "logs": []}

def _check_module(module_name: str) -> bool:
    """Check if a Python module is importable."""
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False

def _check_chromium() -> bool:
    """Check if Playwright Chromium browser is installed."""
    try:
        import pathlib
        # Primary: check ~/.cache/ms-playwright (default location)
        cache_dir = pathlib.Path.home() / ".cache" / "ms-playwright"
        if cache_dir.exists() and any(cache_dir.glob("chromium-*")):
            return True
        # Fallback: check inside playwright package directory
        browser_check = subprocess.run(
            [sys.executable, "-c", "import playwright; import pathlib; browsers = pathlib.Path(playwright.__file__).parent / 'driver' / 'package' / '.local-browsers'; print(any(browsers.glob('chromium-*')) if browsers.exists() else False)"],
            capture_output=True, text=True, timeout=10,
        )
        return "True" in browser_check.stdout
    except Exception:
        return False

@api_router.get("/csdrop/health")
async def csdrop_health_check(user=Depends(security)):
    """Pre-flight check: verify all bot dependencies are available."""
    required_modules = {
        "playwright": "playwright",
        "playwright_stealth": "playwright_stealth",
        "RestrictedPython": "RestrictedPython",
    }
    status = {}
    for display_name, import_name in required_modules.items():
        status[display_name] = "OK" if _check_module(import_name) else "MISSING"

    chromium_ok = _check_chromium()
    status["chromium"] = "OK" if chromium_ok else "MISSING"

    all_ready = all(v == "OK" for v in status.values())
    return {
        "status": status,
        "ready": all_ready,
        "python_path": sys.executable,
        "repair_running": _repair_status["running"],
    }

@api_router.post("/admin/repair")
async def repair_environment(background_tasks: BackgroundTasks):
    """Trigger dependency installation in the background."""
    global _repair_status
    if _repair_status["running"]:
        return {"status": "busy", "message": "Repair already in progress. Check logs."}

    def run_repair():
        global _repair_status
        _repair_status = {"running": True, "last_result": None, "logs": []}
        def _ts():
            return datetime.now(timezone.utc).strftime('%H:%M:%S')

        _repair_status["logs"].append(f"[{_ts()}] Starting system repair...")
        logger.info("Environment repair started")

        # Step 1: pip install bot dependencies
        _repair_status["logs"].append(f"[{_ts()}] Installing Python packages...")
        req_file = CSDROP_BOT_DIR / "requirements.txt"
        if req_file.exists():
            pip_result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
                capture_output=True, text=True, timeout=120,
            )
            if pip_result.returncode == 0:
                _repair_status["logs"].append(f"[{_ts()}] Pip install succeeded.")
            else:
                _repair_status["logs"].append(f"[{_ts()}] Pip install error: {pip_result.stderr[-300:]}")
        else:
            # Fallback: install individually
            pip_result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "playwright", "playwright-stealth", "RestrictedPython"],
                capture_output=True, text=True, timeout=120,
            )
            if pip_result.returncode == 0:
                _repair_status["logs"].append(f"[{_ts()}] Pip install succeeded.")
            else:
                _repair_status["logs"].append(f"[{_ts()}] Pip install error: {pip_result.stderr[-300:]}")

        # Step 2: Install Chromium
        _repair_status["logs"].append(f"[{_ts()}] Installing Chromium browser...")
        chromium_result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True, text=True, timeout=300,
        )
        if chromium_result.returncode == 0:
            _repair_status["logs"].append(f"[{_ts()}] Chromium installed successfully.")
        else:
            _repair_status["logs"].append(f"[{_ts()}] Chromium install error: {chromium_result.stderr[-300:]}")

        # Final status
        all_ok = _check_module("playwright") and _check_module("playwright_stealth") and _check_module("RestrictedPython")
        _repair_status["logs"].append(f"[{_ts()}] Repair complete. All modules OK: {all_ok}")
        _repair_status["running"] = False
        _repair_status["last_result"] = "success" if all_ok else "partial"
        logger.info(f"Environment repair finished. All OK: {all_ok}")

    background_tasks.add_task(run_repair)
    return {"status": "ok", "message": "Repair started in background. Check /api/admin/repair-status for progress."}

@api_router.get("/admin/repair-status")
async def repair_status():
    """Check the status of a running repair job."""
    return {
        "running": _repair_status["running"],
        "last_result": _repair_status["last_result"],
        "logs": _repair_status["logs"][-50:],
    }

async def get_csdrop_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Auth guard that only allows the csdrop client."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(credentials.credentials)
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        if user.get("client_id") != CSDROP_CLIENT_ID:
            raise HTTPException(status_code=403, detail="Access denied. This portal is restricted.")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

class CsdropCodeRun(BaseModel):
    code: str
    input_data: Any = {}

class CsdropBotLaunch(BaseModel):
    promo: str = "https://csdrop.com/r/ABBAS"
    batch: int = 10

@api_router.get("/csdrop/dashboard")
async def csdrop_dashboard(user=Depends(get_csdrop_user)):
    agent_count = await db.user_agents.count_documents({"user_id": user["id"]})
    total_runs = await db.agent_executions.count_documents({"user_id": user["id"]})
    csdrop_execs = await db.csdrop_executions.count_documents({"user_id": user["id"]})
    bot_running = _csdrop_bot_process is not None and _csdrop_bot_process.returncode is None
    return {
        "client": "csdrop",
        "user_name": user.get("name", "CSDROP"),
        "agent_count": agent_count,
        "total_runs": total_runs + csdrop_execs,
        "bot_running": bot_running,
        "bot_log_count": len(_csdrop_bot_logs),
    }

@api_router.post("/csdrop/execute")
async def csdrop_execute_code(data: CsdropCodeRun, user=Depends(get_csdrop_user)):
    from sandbox import execute_code
    result = execute_code(
        code=data.code,
        env_vars={},
        input_data=data.input_data,
    )
    exec_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    exec_doc = {
        "id": exec_id,
        "user_id": user["id"],
        "client_id": CSDROP_CLIENT_ID,
        "code": data.code[:5000],
        "input_data": data.input_data,
        "output": result["output"],
        "result": result["result"],
        "logs": result["logs"],
        "error": result["error"],
        "success": result["success"],
        "duration_ms": result["duration_ms"],
        "created_at": now,
    }
    await db.csdrop_executions.insert_one(exec_doc)
    exec_doc.pop("_id", None)
    return exec_doc

@api_router.get("/csdrop/executions")
async def csdrop_get_executions(user=Depends(get_csdrop_user), limit: int = 30):
    execs = await db.csdrop_executions.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(limit)
    return execs

@api_router.post("/csdrop/launch")
async def csdrop_launch_bot(data: CsdropBotLaunch, user=Depends(get_csdrop_user)):
    global _csdrop_bot_process, _csdrop_bot_logs
    if _csdrop_bot_process and _csdrop_bot_process.returncode is None:
        return {"status": "error", "message": "Bot is already running."}

    # Pre-flight dependency check
    missing = []
    for mod in ["playwright", "playwright_stealth", "RestrictedPython"]:
        if not _check_module(mod):
            missing.append(mod)
    if missing:
        return {"status": "error", "message": f"Missing dependencies: {', '.join(missing)}. Use the Repair button to fix."}

    sovereign_path = CSDROP_BOT_DIR / "sovereign.py"
    if not sovereign_path.exists():
        raise HTTPException(status_code=500, detail="Bot script not found.")

    _csdrop_bot_logs = [f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Launching Sovereign bot..."]
    _csdrop_bot_logs.append(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Promo: {data.promo} | Batch: {data.batch}")

    # Initialize log file
    with open(CSDROP_LOG_FILE, "w") as f:
        for line in _csdrop_bot_logs:
            f.write(line + "\n")

    try:
        _csdrop_bot_process = subprocess.Popen(
            [sys.executable, "-u", str(sovereign_path), data.promo, str(data.batch)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(CSDROP_BOT_DIR),
            text=True,
            bufsize=1,
        )
        # Read output in background — write to both memory and file
        async def _read_output():
            global _csdrop_bot_logs
            loop = aio.get_event_loop()
            while _csdrop_bot_process and _csdrop_bot_process.poll() is None:
                line = await loop.run_in_executor(None, _csdrop_bot_process.stdout.readline)
                if line:
                    ts = datetime.now(timezone.utc).strftime('%H:%M:%S')
                    entry = f"[{ts}] {line.rstrip()}"
                    _csdrop_bot_logs.append(entry)
                    if len(_csdrop_bot_logs) > 500:
                        _csdrop_bot_logs = _csdrop_bot_logs[-300:]
                    # Append to log file
                    try:
                        with open(CSDROP_LOG_FILE, "a") as f:
                            f.write(entry + "\n")
                    except Exception:
                        pass
                else:
                    break
            ts = datetime.now(timezone.utc).strftime('%H:%M:%S')
            entry = f"[{ts}] Bot process ended."
            _csdrop_bot_logs.append(entry)
            try:
                with open(CSDROP_LOG_FILE, "a") as f:
                    f.write(entry + "\n")
            except Exception:
                pass

        aio.create_task(_read_output())
        logger.info(f"CSDROP bot launched by {user['email']}")
        return {"status": "ok", "message": "Sovereign bot launched."}
    except Exception as e:
        logger.error(f"Failed to launch CSDROP bot: {e}")
        return {"status": "error", "message": f"Launch failed: {str(e)}"}

@api_router.post("/csdrop/stop")
async def csdrop_stop_bot(user=Depends(get_csdrop_user)):
    global _csdrop_bot_process, _csdrop_bot_logs
    if not _csdrop_bot_process or _csdrop_bot_process.returncode is not None:
        return {"status": "error", "message": "No bot is currently running."}
    try:
        _csdrop_bot_process.kill()
        _csdrop_bot_process = None
        ts = datetime.now(timezone.utc).strftime('%H:%M:%S')
        _csdrop_bot_logs.append(f"[{ts}] Bot terminated by user.")
        logger.info(f"CSDROP bot stopped by {user['email']}")
        return {"status": "ok", "message": "Bot terminated."}
    except Exception as e:
        return {"status": "error", "message": f"Stop failed: {str(e)}"}

@api_router.get("/csdrop/bot-logs")
async def csdrop_get_bot_logs(user=Depends(get_csdrop_user)):
    bot_running = _csdrop_bot_process is not None and _csdrop_bot_process.returncode is None
    return {
        "running": bot_running,
        "logs": _csdrop_bot_logs[-100:],
    }

@api_router.get("/csdrop/logs")
async def csdrop_get_log_file(user=Depends(get_csdrop_user), lines: int = 50):
    """Read the last N lines from the persistent log file."""
    bot_running = _csdrop_bot_process is not None and _csdrop_bot_process.returncode is None
    if not CSDROP_LOG_FILE.exists():
        return {"running": bot_running, "logs": [], "source": "file", "file": str(CSDROP_LOG_FILE)}
    try:
        with open(CSDROP_LOG_FILE, "r") as f:
            all_lines = f.readlines()
        tail = [line.rstrip() for line in all_lines[-lines:]]
        return {"running": bot_running, "logs": tail, "source": "file", "total_lines": len(all_lines)}
    except Exception as e:
        return {"running": bot_running, "logs": [f"Error reading log: {str(e)}"], "source": "error"}

@api_router.get("/csdrop/live-feed")
async def csdrop_live_feed_status(user=Depends(get_csdrop_user)):
    """Check if a live screenshot is available."""
    feed_path = STATIC_DIR / "live_stream.jpg"
    available = feed_path.exists()
    last_modified = None
    if available:
        last_modified = datetime.fromtimestamp(feed_path.stat().st_mtime, tz=timezone.utc).isoformat()
    bot_running = _csdrop_bot_process is not None and _csdrop_bot_process.returncode is None
    return {
        "available": available,
        "bot_running": bot_running,
        "last_updated": last_modified,
    }

@api_router.get("/csdrop/live-feed/image")
async def csdrop_live_feed_image():
    """Serve the latest bot screenshot. No auth so <img src> works."""
    feed_path = STATIC_DIR / "live_stream.jpg"
    if not feed_path.exists():
        raise HTTPException(status_code=404, detail="No feed available.")
    return FileResponse(
        str(feed_path),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"},
    )

# ─── Session Sync (QR Login) ───
_sync_process = None
_sync_logs = []

@api_router.post("/csdrop/sync-session")
async def csdrop_sync_session(user=Depends(get_csdrop_user)):
    """Start the sovereign.py in --login mode for QR code session sync."""
    global _sync_process, _sync_logs

    # Don't allow if bot is already running
    if _csdrop_bot_process and _csdrop_bot_process.returncode is None:
        return {"status": "error", "message": "Stop the bot first before syncing a new session."}

    # Don't allow if sync already in progress
    if _sync_process and _sync_process.returncode is None:
        return {"status": "error", "message": "Session sync already in progress."}

    # Pre-flight check
    if not _check_module("playwright"):
        return {"status": "error", "message": "Playwright not installed. Run Repair first."}

    sovereign_path = CSDROP_BOT_DIR / "sovereign.py"
    if not sovereign_path.exists():
        raise HTTPException(status_code=500, detail="Bot script not found.")

    # Clean old QR screenshot
    qr_path = STATIC_DIR / "qr_sync.jpg"
    if qr_path.exists():
        qr_path.unlink()

    _sync_logs = [f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Starting session sync..."]

    try:
        _sync_process = subprocess.Popen(
            [sys.executable, "-u", str(sovereign_path), "--login"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(CSDROP_BOT_DIR),
            text=True,
            bufsize=1,
        )

        async def _read_sync_output():
            global _sync_logs
            loop = aio.get_event_loop()
            while _sync_process and _sync_process.poll() is None:
                line = await loop.run_in_executor(None, _sync_process.stdout.readline)
                if line:
                    ts = datetime.now(timezone.utc).strftime('%H:%M:%S')
                    _sync_logs.append(f"[{ts}] {line.rstrip()}")
                    if len(_sync_logs) > 200:
                        _sync_logs = _sync_logs[-100:]
                else:
                    break
            ts = datetime.now(timezone.utc).strftime('%H:%M:%S')
            exit_code = _sync_process.returncode if _sync_process else -1
            if exit_code == 0:
                _sync_logs.append(f"[{ts}] Session sync completed successfully.")
            else:
                _sync_logs.append(f"[{ts}] Session sync ended (exit code: {exit_code}).")

        aio.create_task(_read_sync_output())
        logger.info(f"Session sync started by {user['email']}")
        return {"status": "ok", "message": "Session sync started. Scan the QR code."}
    except Exception as e:
        logger.error(f"Failed to start session sync: {e}")
        return {"status": "error", "message": f"Sync failed: {str(e)}"}

@api_router.get("/csdrop/sync-status")
async def csdrop_sync_status(user=Depends(get_csdrop_user)):
    """Check the status of the session sync process."""
    running = _sync_process is not None and _sync_process.returncode is None
    qr_path = STATIC_DIR / "qr_sync.jpg"
    qr_available = qr_path.exists()

    # Determine outcome
    status = "idle"
    needs_2fa = False
    login_failed = False
    if running:
        status = "syncing"
        # Check if bot is waiting for 2FA
        if any("2FA_REQUIRED" in log for log in _sync_logs):
            needs_2fa = True
            status = "2fa_required"
        # Check if login credentials were rejected
        if any("LOGIN FAILED" in log for log in _sync_logs):
            login_failed = True
            status = "login_failed"
    elif _sync_process is not None:
        has_success = any("SUCCESS" in log for log in _sync_logs)
        has_timeout = any("TIMEOUT" in log for log in _sync_logs)
        has_failed = any("LOGIN FAILED" in log for log in _sync_logs)
        if has_success:
            status = "success"
        elif has_failed:
            status = "login_failed"
        elif has_timeout:
            status = "timeout"
        else:
            status = "finished"

    session_path = CSDROP_BOT_DIR / "discord_session.json"
    session_exists = session_path.exists()
    session_age = None
    if session_exists:
        session_age = datetime.fromtimestamp(session_path.stat().st_mtime, tz=timezone.utc).isoformat()

    return {
        "status": status,
        "qr_available": qr_available,
        "needs_2fa": needs_2fa,
        "login_failed": login_failed,
        "logs": _sync_logs[-30:],
        "session_exists": session_exists,
        "session_last_updated": session_age,
    }

@api_router.post("/csdrop/sync-stop")
async def csdrop_sync_stop(user=Depends(get_csdrop_user)):
    """Cancel an in-progress session sync."""
    global _sync_process, _sync_logs
    if not _sync_process or _sync_process.returncode is not None:
        return {"status": "error", "message": "No sync in progress."}
    try:
        _sync_process.kill()
        _sync_process = None
        ts = datetime.now(timezone.utc).strftime('%H:%M:%S')
        _sync_logs.append(f"[{ts}] Sync cancelled by user.")
        # Clean up QR
        qr_path = STATIC_DIR / "qr_sync.jpg"
        if qr_path.exists():
            qr_path.unlink()
        return {"status": "ok", "message": "Sync cancelled."}
    except Exception as e:
        return {"status": "error", "message": f"Stop failed: {str(e)}"}

@api_router.get("/csdrop/sync-qr")
async def csdrop_sync_qr_image():
    """Serve the QR code screenshot. No auth so <img src> works."""
    qr_path = STATIC_DIR / "qr_sync.jpg"
    if not qr_path.exists():
        raise HTTPException(status_code=404, detail="No QR code available.")
    return FileResponse(
        str(qr_path),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"},
    )

# ─── Manual Login (Email/Password + 2FA) ───

class ManualLoginData(BaseModel):
    email: str
    password: str

class TwoFAData(BaseModel):
    code: str

@api_router.post("/csdrop/manual-login")
async def csdrop_manual_login(data: ManualLoginData, user=Depends(get_csdrop_user)):
    """Start sovereign.py in --manual mode with provided credentials."""
    global _sync_process, _sync_logs

    if _csdrop_bot_process and _csdrop_bot_process.returncode is None:
        return {"status": "error", "message": "Stop the bot first."}
    if _sync_process and _sync_process.returncode is None:
        return {"status": "error", "message": "A sync is already in progress."}
    if not _check_module("playwright"):
        return {"status": "error", "message": "Playwright not installed. Run Repair first."}

    sovereign_path = CSDROP_BOT_DIR / "sovereign.py"
    if not sovereign_path.exists():
        raise HTTPException(status_code=500, detail="Bot script not found.")

    # Write credentials to a temp file (bot reads and deletes immediately)
    creds_file = CSDROP_BOT_DIR / "manual_creds.json"
    creds_file.write_text(json.dumps({"email": data.email, "password": data.password}))

    # Clean old QR/signal files
    qr_path = STATIC_DIR / "qr_sync.jpg"
    signal_file = CSDROP_BOT_DIR / "2fa_signal.txt"
    for f in [qr_path, signal_file]:
        if f.exists():
            f.unlink()

    _sync_logs = [f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Starting manual login for {data.email}..."]

    try:
        _sync_process = subprocess.Popen(
            [sys.executable, "-u", str(sovereign_path), "--manual"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(CSDROP_BOT_DIR),
            text=True,
            bufsize=1,
        )

        async def _read_sync_output():
            global _sync_logs
            loop = aio.get_event_loop()
            while _sync_process and _sync_process.poll() is None:
                line = await loop.run_in_executor(None, _sync_process.stdout.readline)
                if line:
                    ts = datetime.now(timezone.utc).strftime('%H:%M:%S')
                    _sync_logs.append(f"[{ts}] {line.rstrip()}")
                    if len(_sync_logs) > 200:
                        _sync_logs = _sync_logs[-100:]
                else:
                    break
            ts = datetime.now(timezone.utc).strftime('%H:%M:%S')
            exit_code = _sync_process.returncode if _sync_process else -1
            if exit_code == 0:
                _sync_logs.append(f"[{ts}] Manual login completed successfully.")
            else:
                _sync_logs.append(f"[{ts}] Manual login ended (exit code: {exit_code}).")

        aio.create_task(_read_sync_output())
        logger.info(f"Manual login started by {user['email']}")
        return {"status": "ok", "message": "Manual login started. Entering credentials..."}
    except Exception as e:
        # Clean up creds file on error
        creds_file.unlink(missing_ok=True)
        return {"status": "error", "message": f"Failed: {str(e)}"}

@api_router.post("/csdrop/submit-2fa")
async def csdrop_submit_2fa(data: TwoFAData, user=Depends(get_csdrop_user)):
    """Write the 2FA code to a signal file for the bot to pick up."""
    if not _sync_process or _sync_process.returncode is not None:
        return {"status": "error", "message": "No login process running."}

    code = data.code.strip()
    if not code or len(code) < 4 or len(code) > 8:
        return {"status": "error", "message": "Invalid code. Must be 4-8 digits."}

    signal_file = CSDROP_BOT_DIR / "2fa_signal.txt"
    signal_file.write_text(code)
    logger.info(f"2FA code submitted by {user['email']}")
    return {"status": "ok", "message": "2FA code submitted. Bot will enter it now."}

@api_router.get("/csdrop/error-screenshot")
async def csdrop_error_screenshot():
    """Serve the last error screenshot. No auth so <img src> works."""
    err_path = STATIC_DIR / "error_last.jpg"
    if not err_path.exists():
        raise HTTPException(status_code=404, detail="No error screenshot available.")
    return FileResponse(
        str(err_path),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"},
    )


@api_router.get("/csdrop/debug-render")
async def csdrop_debug_render():
    """Serve the debug render screenshot. No auth so <img src> works."""
    dbg_path = STATIC_DIR / "debug_render.jpg"
    if not dbg_path.exists():
        raise HTTPException(status_code=404, detail="No debug render available.")
    return FileResponse(
        str(dbg_path),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"},
    )

@api_router.get("/csdrop/cycle-timeout")
async def csdrop_cycle_timeout_screenshot():
    """Serve the cycle timeout debug screenshot. No auth so <img src> works."""
    path = STATIC_DIR / "cycle_timeout_debug.jpg"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No timeout screenshot available.")
    return FileResponse(
        str(path),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"},
    )


@api_router.get("/csdrop/agents")
async def csdrop_list_agents(user=Depends(get_csdrop_user)):
    agents = await db.user_agents.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("updated_at", -1).to_list(50)
    return agents

@api_router.post("/csdrop/agents")
async def csdrop_create_agent(data: UserAgentCreate, user=Depends(get_csdrop_user)):
    count = await db.user_agents.count_documents({"user_id": user["id"]})
    if count >= 10:
        raise HTTPException(status_code=403, detail="Agent limit reached (10).")
    from sandbox import validate_code
    err = validate_code(data.code)
    if err:
        raise HTTPException(status_code=400, detail=f"Code validation failed: {err}")
    agent_id = str(uuid.uuid4())
    webhook_key = secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": agent_id, "user_id": user["id"],
        "name": data.name, "description": data.description,
        "code": data.code, "env_vars": data.env_vars,
        "trigger_type": data.trigger_type, "webhook_key": webhook_key,
        "status": "ready", "last_run": None, "last_result": None,
        "run_count": 0, "created_at": now, "updated_at": now,
    }
    await db.user_agents.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.delete("/csdrop/agents/{agent_id}")
async def csdrop_delete_agent(agent_id: str, user=Depends(get_csdrop_user)):
    result = await db.user_agents.delete_one({"id": agent_id, "user_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"message": "Agent deleted"}

@api_router.post("/csdrop/agents/{agent_id}/run")
async def csdrop_run_agent(agent_id: str, data: AgentRunRequest, user=Depends(get_csdrop_user)):
    agent = await db.user_agents.find_one({"id": agent_id, "user_id": user["id"]}, {"_id": 0})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    from sandbox import execute_code
    result = execute_code(code=agent["code"], env_vars=agent["env_vars"], input_data=data.input_data)
    exec_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    exec_doc = {
        "id": exec_id, "agent_id": agent_id, "user_id": user["id"],
        "trigger": "manual", "input_data": data.input_data,
        "output": result["output"], "result": result["result"],
        "logs": result["logs"], "error": result["error"],
        "success": result["success"], "duration_ms": result["duration_ms"],
        "created_at": now,
    }
    await db.agent_executions.insert_one(exec_doc)
    exec_doc.pop("_id", None)
    await db.user_agents.update_one({"id": agent_id}, {"$set": {
        "last_run": now, "last_result": "success" if result["success"] else "error",
        "updated_at": now,
    }, "$inc": {"run_count": 1}})
    return exec_doc

# ─── Stripe Payment Endpoints ───

AGENT_PACKAGES = {}  # populated dynamically from DB

@api_router.post("/payments/checkout")
async def create_checkout(request: Request, data: dict, user=Depends(get_current_user)):
    agent_id = data.get("agent_id")
    plan = data.get("plan", "rent")  # "rent" or "buy"
    origin_url = data.get("origin_url", "")

    if not origin_url:
        raise HTTPException(status_code=400, detail="origin_url is required")

    agent = await db.agents.find_one({"id": agent_id}, {"_id": 0})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Price from server-side only
    amount = float(agent["price"]) if plan == "rent" else float(agent["buyPrice"])
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid price")

    success_url = f"{origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin_url}/agent/{agent_id}"

    stripe_key = os.environ.get("STRIPE_API_KEY")
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=stripe_key, webhook_url=webhook_url)

    checkout_req = CheckoutSessionRequest(
        amount=amount,
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "agent_id": str(agent_id),
            "agent_name": agent["shortTitle"],
            "plan": plan,
            "user_id": user["id"],
            "user_email": user["email"],
        },
    )
    session = await stripe_checkout.create_checkout_session(checkout_req)

    # Create payment transaction record
    tx_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await db.payment_transactions.insert_one({
        "id": tx_id,
        "session_id": session.session_id,
        "user_id": user["id"],
        "user_email": user["email"],
        "agent_id": agent_id,
        "agent_name": agent["shortTitle"],
        "plan": plan,
        "amount": amount,
        "currency": "usd",
        "payment_status": "pending",
        "created_at": now,
        "updated_at": now,
    })

    return {"url": session.url, "session_id": session.session_id}

@api_router.get("/payments/status/{session_id}")
async def get_payment_status(session_id: str, request: Request):
    tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    stripe_key = os.environ.get("STRIPE_API_KEY")
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=stripe_key, webhook_url=webhook_url)

    status = await stripe_checkout.get_checkout_status(session_id)

    if status.payment_status != tx.get("payment_status"):
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {
                "payment_status": status.payment_status,
                "status": status.status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

    return {
        "session_id": session_id,
        "status": status.status,
        "payment_status": status.payment_status,
        "amount": status.amount_total,
        "currency": status.currency,
        "agent_id": tx.get("agent_id"),
        "agent_name": tx.get("agent_name"),
        "plan": tx.get("plan"),
    }

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    stripe_key = os.environ.get("STRIPE_API_KEY")
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=stripe_key, webhook_url=webhook_url)

    try:
        event = await stripe_checkout.handle_webhook(body, sig)
        if event.payment_status == "paid" and event.session_id:
            tx = await db.payment_transactions.find_one({"session_id": event.session_id})
            if tx and tx.get("payment_status") != "paid":
                await db.payment_transactions.update_one(
                    {"session_id": event.session_id},
                    {"$set": {
                        "payment_status": "paid",
                        "status": "complete",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }},
                )
                logger.info(f"Payment confirmed for session {event.session_id}")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error"}

# ─── Health ───

@api_router.get("/")
async def root():
    return {"message": "Nova AI API", "status": "ok"}

# Include router
app.include_router(api_router)

# Mount static files for live bot screenshots
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    # Auto-seed on startup
    count = await db.agents.count_documents({})
    if count == 0:
        logger.info("No data found, seeding database...")
        await seed_database()
    admin = await db.users.find_one({"email": "admin@nova.ai"})
    if not admin:
        admin_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await db.users.insert_one({
            "id": admin_id, "email": "admin@nova.ai",
            "password_hash": hash_password("admin123"),
            "name": "Nova Admin", "role": "admin", "created_at": now,
        })
        logger.info("Admin user created")

    # Seed CSDROP client user
    csdrop_user = await db.users.find_one({"client_id": "csdrop"})
    if not csdrop_user:
        csdrop_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await db.users.insert_one({
            "id": csdrop_id, "email": "admin@csdrop.com",
            "password_hash": hash_password("nova_csdrop_2026"),
            "name": "CSDROP", "role": "client", "client_id": "csdrop",
            "tier": "pro", "created_at": now,
        })
        logger.info("CSDROP client user created")

    # Ensure csdrop_executions collection index
    await db.csdrop_executions.create_index("user_id")

    # Start Supernova scheduler (runs daily at midnight)
    scheduler.add_job(evaluate_supernovas, 'interval', hours=24, id='supernova_eval', replace_existing=True)
    scheduler.start()
    logger.info("Supernova scheduler started")

    # Run initial evaluation
    await evaluate_supernovas()

    # ─── Startup Health Check + Auto-Repair ───
    logger.info("Running environment health check...")
    missing_modules = []
    for mod_name, import_name in [("playwright", "playwright"), ("playwright_stealth", "playwright_stealth"), ("RestrictedPython", "RestrictedPython")]:
        if _check_module(import_name):
            logger.info(f"  [OK] {mod_name}")
        else:
            logger.warning(f"  [MISSING] {mod_name}")
            missing_modules.append(mod_name)

    chromium_ok = _check_chromium()
    if chromium_ok:
        logger.info("  [OK] chromium")
    else:
        logger.warning("  [MISSING] chromium")
        missing_modules.append("chromium")

    logger.info(f"Python executable: {sys.executable}")

    if missing_modules:
        logger.info(f"Auto-repair triggered for: {', '.join(missing_modules)}")

        def _startup_repair():
            global _repair_status
            _repair_status = {"running": True, "last_result": None, "logs": []}
            def _ts():
                return datetime.now(timezone.utc).strftime('%H:%M:%S')

            _repair_status["logs"].append(f"[{_ts()}] Auto-repair on startup...")
            logger.info("Startup auto-repair: installing dependencies...")

            req_file = CSDROP_BOT_DIR / "requirements.txt"
            if req_file.exists():
                pip_result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
                    capture_output=True, text=True, timeout=120,
                )
                _repair_status["logs"].append(f"[{_ts()}] Pip: {'OK' if pip_result.returncode == 0 else 'FAIL'}")

            if not chromium_ok:
                chromium_result = subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "chromium"],
                    capture_output=True, text=True, timeout=300,
                )
                _repair_status["logs"].append(f"[{_ts()}] Chromium: {'OK' if chromium_result.returncode == 0 else 'FAIL'}")

            all_ok = all(_check_module(m) for m in ["playwright", "playwright_stealth", "RestrictedPython"])
            _repair_status["logs"].append(f"[{_ts()}] Auto-repair complete. All OK: {all_ok}")
            _repair_status["running"] = False
            _repair_status["last_result"] = "success" if all_ok else "partial"
            logger.info(f"Startup auto-repair finished. All OK: {all_ok}")

        import threading
        threading.Thread(target=_startup_repair, daemon=True).start()
    else:
        logger.info("All dependencies OK. No repair needed.")

@app.on_event("shutdown")
async def shutdown_db_client():
    scheduler.shutdown(wait=False)
    client.close()
