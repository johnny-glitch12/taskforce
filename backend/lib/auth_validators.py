"""
auth_validators — Username + password validation rules.

Used by /api/auth/register (server-side enforcement) and /api/auth/check-username.
The frontend mirrors these rules for instant UX (strength meter + checklist) but
the backend is the source of truth — never trust the client.

Design notes:
  - Validators return a structured object so the frontend can render the
    GitHub-style "✓/✗ Number" checklist without re-running the same regex on
    each keystroke. Callers that just want a bool/raise pattern wrap these.
  - Reserved usernames are matched case-insensitively against username_lower.
  - The password "score" (0..4) maps to {Weak, Fair, Good, Strong} on the FE.
"""
from __future__ import annotations

import re
from typing import Optional

# ─── Constants ──────────────────────────────────────────
RESERVED_USERNAMES = {
    "admin", "root", "system", "taskforce", "support", "help", "api",
    "null", "undefined", "moderator", "mod", "staff", "official",
    # A few extras commonly grabbed by squatters / look-alikes
    "administrator", "superuser", "test", "anonymous", "guest", "me",
}

USERNAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{2,19}$")
# (Starts with letter · 3-20 total · letters/digits/underscore only)

# Special chars allowed in passwords. Mirrors what we tell users in the UI.
SPECIAL_CHARS_RE = re.compile(r"[!@#$%^&*()_+\-=\[\]{}|;:',.<>?/\\]")


# ─── Password ──────────────────────────────────────────
def check_password(password: str, username: str = "", email: str = "") -> dict:
    """Return a structured rule-check object. NEVER raises.

    Output shape (consumed by both backend register() and FE strength meter):
        {
          "ok": bool,                      # all hard rules met
          "errors": ["Password must …"],   # human-readable
          "rules": {                       # per-rule pass/fail, for checklist
              "length": bool, "uppercase": bool, "lowercase": bool,
              "number": bool, "special": bool, "no_whitespace_trim": bool,
              "not_username_or_email": bool, "max_length": bool,
          },
          "score": 0..4,                   # Weak/Fair/Good/Strong tier
        }
    """
    rules = {
        "length": len(password) >= 8,
        "uppercase": bool(re.search(r"[A-Z]", password)),
        "lowercase": bool(re.search(r"[a-z]", password)),
        "number": bool(re.search(r"[0-9]", password)),
        "special": bool(SPECIAL_CHARS_RE.search(password)),
        "max_length": len(password) <= 128,
        "no_whitespace_trim": password == password.strip(),
        "not_username_or_email": (
            password.lower() != (username or "").lower()
            and password.lower() != (email or "").lower()
            # Also block "password is the local part of the email" — very common.
            and password.lower() != (email or "").split("@", 1)[0].lower()
        ),
    }

    errors: list[str] = []
    if not rules["length"]:
        errors.append("Password must be at least 8 characters.")
    if not rules["max_length"]:
        errors.append("Password must be 128 characters or fewer.")
    if not rules["uppercase"]:
        errors.append("Password must contain at least one uppercase letter.")
    if not rules["lowercase"]:
        errors.append("Password must contain at least one lowercase letter.")
    if not rules["number"]:
        errors.append("Password must contain at least one number.")
    if not rules["special"]:
        errors.append("Password must contain at least one special character.")
    if not rules["no_whitespace_trim"]:
        errors.append("Password cannot start or end with whitespace.")
    if not rules["not_username_or_email"]:
        errors.append("Password cannot be the same as your username or email.")

    # Score buckets for the strength meter. Independent from `ok` because the
    # meter should still show "Fair" or "Good" while the user is mid-typing
    # even though `ok=False`.
    char_type_count = sum(rules[k] for k in ("uppercase", "lowercase", "number", "special"))
    score = 0
    if rules["length"]:
        if char_type_count >= 4 and len(password) >= 12:
            score = 4  # Strong
        elif char_type_count >= 3:
            score = 3  # Good
        elif char_type_count >= 2:
            score = 2  # Fair
        else:
            score = 1  # Weak (length-only)

    ok = all(rules.values())
    return {"ok": ok, "errors": errors, "rules": rules, "score": score}


# ─── Username ──────────────────────────────────────────
def check_username(username: str) -> dict:
    """Return per-rule pass/fail + human-readable errors. NEVER raises."""
    u = (username or "").strip()
    rules = {
        "length": 3 <= len(u) <= 20,
        "format": bool(USERNAME_RE.match(u)),
        "starts_with_letter": bool(u) and u[0].isalpha(),
        "not_reserved": u.lower() not in RESERVED_USERNAMES,
    }
    errors: list[str] = []
    if not rules["length"]:
        errors.append("Username must be 3-20 characters.")
    if not rules["format"]:
        errors.append("Username can only contain letters, numbers, and underscores.")
    if not rules["starts_with_letter"]:
        errors.append("Username must start with a letter.")
    if not rules["not_reserved"]:
        errors.append("That username is reserved.")
    return {"ok": all(rules.values()), "errors": errors, "rules": rules}


# ─── Bulk validation for /register ─────────────────────
def validate_signup(*, username: str, email: str, password: str) -> dict:
    """Returns {"ok": bool, "errors": [str], "details": {username:..., password:...}}.
    Caller raises 422 if not ok."""
    u_check = check_username(username)
    p_check = check_password(password, username=username, email=email)
    errors = list(u_check["errors"]) + list(p_check["errors"])
    return {
        "ok": u_check["ok"] and p_check["ok"],
        "errors": errors,
        "details": {"username": u_check, "password": p_check},
    }
