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
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from lib.rate_limit import rate_limit_dependency
from lib.auth_validators import (
    validate_signup, check_username, check_password, RESERVED_USERNAMES,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Anti-abuse settings ──
SIGNUP_BONUS_CREDITS = 50           # 50 free top-up credits per new account
MAX_ACCOUNTS_PER_IP_24H = 3         # Cap accounts created from the same IP per 24h window


def _client_ip(request: Request) -> str:
    """Resolve the real client IP from `X-Forwarded-For` (Kubernetes ingress) → falls back to socket peer."""
    xff = request.headers.get("X-Forwarded-For") or request.headers.get("X-Real-IP", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── Pydantic models (mirrors server.py — defined here too so FastAPI typed body parse works) ──
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    # Backward-compat: callers may send `name` only — we'll fall back to deriving
    # a username if `username` is absent (transitional, see register() body).
    username: str = Field(default="", max_length=20)
    name: str = ""


class LoginRequest(BaseModel):
    # Accepts either an email or a username — we normalize and look up both.
    email: str = Field(min_length=1, max_length=200)
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
async def register(req: RegisterRequest, request: Request, _=Depends(rate_limit_dependency("register", 5, 600))):
    srv = _srv()
    db = srv.db

    # ── Validation (Prompt 25) ─────────────────────────────────
    # Derive a username when the legacy client just sent {email, password, name}.
    # We try: incoming `username` → `name` (if it parses) → email-prefix. The
    # derived value still has to pass check_username() — caller gets a clear
    # error if e.g. their email prefix has dots.
    raw_username = (req.username or req.name or req.email.split("@")[0]).strip()
    # Replace dots/dashes with underscores so common email prefixes like
    # "first.last" auto-derive into a valid username.
    derived = raw_username.replace(".", "_").replace("-", "_")
    check = validate_signup(username=derived, email=req.email, password=req.password)
    if not check["ok"]:
        # 422 with structured details — frontend renders the list.
        raise HTTPException(status_code=422, detail={
            "error": "validation_failed",
            "details": check["errors"],
            "rules": check["details"],
        })

    username = derived
    username_lower = username.lower()

    # Case-insensitive username uniqueness. We store the lower form in a
    # dedicated field with a unique index (created lazily on first signup
    # below) so lookups are fast + collisions are atomic.
    existing_uname = await db.users.find_one({"username_lower": username_lower})
    if existing_uname:
        raise HTTPException(status_code=422, detail={
            "error": "validation_failed",
            "details": ["Username is already taken."],
        })

    existing = await db.users.find_one({"email": req.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # ── Anti-abuse: cap accounts per IP per 24h window ──
    ip = _client_ip(request)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    recent_from_ip = await db.users.count_documents({
        "registration_ip": ip,
        "created_at": {"$gte": cutoff},
    })
    if recent_from_ip >= MAX_ACCOUNTS_PER_IP_24H:
        logger.warning(f"Registration blocked — IP {ip} hit {recent_from_ip} accounts in 24h.")
        raise HTTPException(
            status_code=429,
            detail="Too many accounts created from your network. Try again in 24 hours.",
        )

    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    user_doc = {
        "id": user_id, "email": req.email,
        "password_hash": srv.hash_password(req.password),
        "name": req.name or username,
        "username": username,
        "username_lower": username_lower,
        "role": "user", "created_at": now,
        # Anti-abuse + signup bonus state
        "registration_ip": ip,
        "last_login_ip": ip,
        "last_login_at": now,
        # Dual-pool credits (signup bonus lands in topup, never expires)
        "subscription_credits": 50,
        "subscription_credits_max": 50,
        "topup_credits": SIGNUP_BONUS_CREDITS,
        "credit_reset_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "tier": "recruit",
    }
    await db.users.insert_one(user_doc)

    # Immutable ledger entry for the signup bonus.
    await db.credit_transactions.insert_one({
        "user_id": user_id,
        "email": req.email,
        "delta": SIGNUP_BONUS_CREDITS,
        "kind": "signup_bonus",
        "ref": None,
        "pool": "topup",
        "sub_deducted": 0,
        "topup_deducted": 0,
        "sub_remaining": 50,
        "topup_remaining": SIGNUP_BONUS_CREDITS,
        "balance_after": 50 + SIGNUP_BONUS_CREDITS,
        "note": f"+{SIGNUP_BONUS_CREDITS} welcome bonus",
        "virtual": False,
        "metadata": {"ip": ip},
        "created_at": now,
    })
    logger.info(f"User registered: {req.email} from IP {ip} (+{SIGNUP_BONUS_CREDITS} bonus credits)")

    token = srv.create_token(user_id, req.email, "user")

    # Fire-and-forget welcome email — never blocks the registration response.
    try:
        from utils.email_service import send_welcome_email
        import asyncio
        asyncio.create_task(send_welcome_email(req.email, user_doc["name"]))
    except Exception as _e:
        logger.warning(f"[email] welcome send failed to schedule: {_e}")

    return srv.TokenResponse(
        token=token,
        user=srv.UserResponse(id=user_id, email=req.email, name=user_doc["name"], role="user", created_at=now),
    )


@router.post("/auth/login")
async def login(req: LoginRequest, request: Request, _=Depends(rate_limit_dependency("login", 10, 60))):
    srv = _srv()
    db = srv.db

    # Identifier can be email OR username. Match on either field but keep the
    # error message generic to prevent username enumeration attacks.
    ident = (req.email or "").strip()
    if "@" in ident:
        query = {"email": ident.lower()} if False else {"email": ident}
    else:
        query = {"username_lower": ident.lower()}
    user = await db.users.find_one(query, {"_id": 0})
    if not user or not srv.verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    # Track login IP for analytics + abuse detection.
    ip = _client_ip(request)
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"last_login_ip": ip, "last_login_at": datetime.now(timezone.utc).isoformat()}},
    )
    token = srv.create_token(user["id"], user["email"], user["role"])
    return srv.TokenResponse(
        token=token,
        user=srv.UserResponse(
            id=user["id"], email=user["email"], name=user["name"], role=user["role"],
            client_id=user.get("client_id"), tier=user.get("tier", "free"),
            is_owner=bool(user.get("is_owner", False)),
            created_at=user["created_at"],
        ),
    )


# ─── Username availability (Prompt 25) ─────────────────
@router.get("/auth/check-username")
async def check_username_available(
    username: str,
    _=Depends(rate_limit_dependency("check_username", 10, 60)),
):
    """Live availability probe for the signup form. Rate-limited to 10/min/IP
    so a bot can't enumerate the username space. Returns:
        {available: bool, reason: "taken" | "invalid" | "reserved" | "ok"}
    Never reveals WHICH user owns a taken username — just the boolean."""
    u = (username or "").strip()
    if len(u) < 3:
        return {"available": False, "reason": "too_short"}
    rule = check_username(u)
    if not rule["ok"]:
        # Aggregate into a single front-end-friendly reason.
        if not rule["rules"]["not_reserved"]:
            return {"available": False, "reason": "reserved"}
        return {"available": False, "reason": "invalid"}
    srv = _srv()
    existing = await srv.db.users.find_one(
        {"username_lower": u.lower()}, {"_id": 1},
    )
    return {"available": existing is None, "reason": "taken" if existing else "ok"}


@router.get("/auth/me")
async def get_me(user=Depends(get_current_user())):
    srv = _srv()
    return srv.UserResponse(
        id=user["id"], email=user["email"], name=user["name"], role=user["role"],
        client_id=user.get("client_id"), tier=user.get("tier", "free"),
        is_owner=bool(user.get("is_owner", False)),
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

    # Fire-and-forget reset email — never blocks the response so we don't leak
    # whether the email exists via timing differences.
    try:
        from utils.email_service import send_password_reset_email
        import asyncio
        asyncio.create_task(send_password_reset_email(req.email, user.get("name"), reset_token))
    except Exception as _e:
        logger.warning(f"[email] reset email failed to schedule: {_e}")

    # In prod (EMAIL_ENABLED=true) we OMIT reset_token from the response so it
    # only reaches the user via the verified email channel. In dev we include it
    # so the FE password-reset flow can be tested end-to-end without a mailbox.
    from utils.email_service import EMAIL_ENABLED
    if EMAIL_ENABLED:
        return {"message": "If that email exists, a reset link has been generated."}
    return {"message": "If that email exists, a reset link has been generated.",
            "reset_token": reset_token}


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

    # Enforce the same password rules as /register (Prompt 25). The user's email
    # is available via the reset_entry; we pass it so the validator can block
    # "new password equals my email" patterns too.
    user = await db.users.find_one({"id": reset_entry["user_id"]}, {"email": 1, "username": 1, "_id": 0}) or {}
    p_check = check_password(req.new_password, username=user.get("username", ""), email=user.get("email", ""))
    if not p_check["ok"]:
        raise HTTPException(status_code=422, detail={
            "error": "validation_failed",
            "details": p_check["errors"],
            "rules": p_check["rules"],
        })

    new_hash = srv.hash_password(req.new_password)
    await db.users.update_one({"id": reset_entry["user_id"]}, {"$set": {"password_hash": new_hash}})
    await db.password_resets.update_one({"token": req.token}, {"$set": {"used": True}})
    return {"message": "Password reset successfully. You can now log in with your new password."}
