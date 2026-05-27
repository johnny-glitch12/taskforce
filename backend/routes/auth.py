"""
Auth Routes — Task Force AI

Extracted from server.py. Uses Pydantic models directly for 422 validation
errors. EmailStr + Field constraints ensure malformed payloads fail before
hitting the route body.
"""
import uuid
import secrets
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from lib.rate_limit import rate_limit_dependency

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Pydantic models (mirrors server.py — defined here too so FastAPI typed body parse works) ──
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ForgotRequest(BaseModel):
    email: EmailStr


class ResetRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


def get_current_user():
    from server import get_current_user as _u
    return _u


def _srv():
    import server as srv
    return srv


@router.post("/auth/register")
async def register(req: RegisterRequest, _=Depends(rate_limit_dependency("register", 5, 600))):
    srv = _srv()
    db = srv.db

    existing = await db.users.find_one({"email": req.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    user_doc = {
        "id": user_id, "email": req.email,
        "password_hash": srv.hash_password(req.password),
        "name": req.name or req.email.split("@")[0],
        "role": "user", "created_at": now,
    }
    await db.users.insert_one(user_doc)
    token = srv.create_token(user_id, req.email, "user")
    return srv.TokenResponse(
        token=token,
        user=srv.UserResponse(id=user_id, email=req.email, name=user_doc["name"], role="user", created_at=now),
    )


@router.post("/auth/login")
async def login(req: LoginRequest, _=Depends(rate_limit_dependency("login", 10, 60))):
    srv = _srv()
    db = srv.db

    user = await db.users.find_one({"email": req.email}, {"_id": 0})
    if not user or not srv.verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = srv.create_token(user["id"], user["email"], user["role"])
    return srv.TokenResponse(
        token=token,
        user=srv.UserResponse(
            id=user["id"], email=user["email"], name=user["name"], role=user["role"],
            client_id=user.get("client_id"), tier=user.get("tier", "free"),
            created_at=user["created_at"],
        ),
    )


@router.get("/auth/me")
async def get_me(user=Depends(get_current_user())):
    srv = _srv()
    return srv.UserResponse(
        id=user["id"], email=user["email"], name=user["name"], role=user["role"],
        client_id=user.get("client_id"), tier=user.get("tier", "free"),
        created_at=user["created_at"],
    )


@router.post("/auth/forgot-password")
async def forgot_password(req: ForgotRequest, _=Depends(rate_limit_dependency("forgot", 3, 600))):
    srv = _srv()
    db = srv.db

    user = await db.users.find_one({"email": req.email}, {"_id": 0})
    if not user:
        return {"message": "If that email exists, a reset link has been generated.", "reset_token": None}

    reset_token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    await db.password_resets.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "email": req.email,
        "token": reset_token,
        "expires_at": expires.isoformat(),
        "used": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    logger.info(f"Password reset token generated for {req.email}")
    return {"message": "If that email exists, a reset link has been generated.", "reset_token": reset_token}


@router.post("/auth/reset-password")
async def reset_password(req: ResetRequest):
    srv = _srv()
    db = srv.db

    reset_entry = await db.password_resets.find_one({"token": req.token, "used": False}, {"_id": 0})
    if not reset_entry:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    expires = datetime.fromisoformat(reset_entry["expires_at"])
    if datetime.now(timezone.utc) > expires:
        raise HTTPException(status_code=400, detail="Reset token has expired")
    new_hash = srv.hash_password(req.new_password)
    await db.users.update_one({"id": reset_entry["user_id"]}, {"$set": {"password_hash": new_hash}})
    await db.password_resets.update_one({"token": req.token}, {"$set": {"used": True}})
    return {"message": "Password reset successfully. You can now log in with your new password."}
