from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext

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
    created_at: str

class TokenResponse(BaseModel):
    token: str
    user: UserResponse

class WaitlistCreate(BaseModel):
    email: str

class WaitlistResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    created_at: str

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

class ReviewResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    agent_id: int
    user_name: str
    rating: int
    date: str
    text: str

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
        user=UserResponse(id=user["id"], email=user["email"], name=user["name"], role=user["role"], created_at=user["created_at"])
    )

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(user=Depends(get_current_user)):
    return UserResponse(id=user["id"], email=user["email"], name=user["name"], role=user["role"], created_at=user["created_at"])

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
        ]
    agents = await db.agents.find(query, {"_id": 0}).sort("deployCount", -1).to_list(100)
    return agents

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
        {"id": "datawiz", "name": "Sarah Chen", "username": "@DataWiz", "initial": "S", "color": "#8B5CF6", "verified": True, "trustScore": 99, "heroStat": "1.2k+ Agents Deployed", "topCategory": "Top Rated in Data", "bio": "Former data scientist at Stripe. Building the future of automated analytics.", "responseTime": "< 1 hour", "memberSince": "Jan 2025", "completionRate": "99%", "agentPreviews": ["Data Analyst", "ETL Pipeline", "Anomaly Detector"]},
        {"id": "salesforge", "name": "Marcus Rivera", "username": "@SalesForge", "initial": "M", "color": "#6D28D9", "verified": True, "trustScore": 97, "heroStat": "890+ Agents Deployed", "topCategory": "Top Rated in Sales", "bio": "Ex-VP Sales at HubSpot. Automating the entire outbound pipeline.", "responseTime": "< 2 hours", "memberSince": "Mar 2025", "completionRate": "98%", "agentPreviews": ["Sales Dev Rep", "Lead Qualifier", "Outbound Pro"]},
        {"id": "cxmaster", "name": "Priya Sharma", "username": "@CXMaster", "initial": "P", "color": "#7C3AED", "verified": True, "trustScore": 98, "heroStat": "1.5k+ Agents Deployed", "topCategory": "#1 in Support", "bio": "Built CX teams at Zendesk and Intercom. Now building agents that scale empathy.", "responseTime": "< 30 min", "memberSince": "Dec 2024", "completionRate": "100%", "agentPreviews": ["Customer Service Pro", "Ticket Triage", "CSAT Analyst"]},
        {"id": "codepilot", "name": "Alex Dubois", "username": "@CodePilot", "initial": "A", "color": "#A78BFA", "verified": True, "trustScore": 96, "heroStat": "640+ Agents Deployed", "topCategory": "Top Rated in Coding", "bio": "Staff engineer turned agent builder. Making code reviews 10x faster.", "responseTime": "< 3 hours", "memberSince": "Feb 2025", "completionRate": "97%", "agentPreviews": ["Code Reviewer", "CI/CD Agent", "Bug Triager"]},
        {"id": "financeai", "name": "James Okonkwo", "username": "@FinanceAI", "initial": "J", "color": "#5B21B6", "verified": True, "trustScore": 99, "heroStat": "720+ Agents Deployed", "topCategory": "#1 in Finance", "bio": "CPA + ML engineer. Building enterprise-grade compliance automation.", "responseTime": "< 1 hour", "memberSince": "Nov 2024", "completionRate": "100%", "agentPreviews": ["Finance Auditor", "Expense Tracker", "Risk Scorer"]},
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

    # Seed reviews (for all agents)
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

    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.waitlist.create_index("email", unique=True)
    await db.agents.create_index("id", unique=True)
    await db.agents.create_index("category")
    await db.creators.create_index("id", unique=True)
    await db.reviews.create_index("agent_id")

    logger.info("Database seeded successfully")
    return {"message": "Database seeded", "agents": len(agents_data), "creators": len(creators_data), "reviews": len(reviews_data)}

# ─── Health ───

@api_router.get("/")
async def root():
    return {"message": "Nova AI API", "status": "ok"}

# Include router
app.include_router(api_router)

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

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()