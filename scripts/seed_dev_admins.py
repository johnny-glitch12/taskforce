"""One-shot seed script — creates 7 early-dev admin accounts and marks
admin@nova.ai as the platform owner.

Usage:
    python /app/scripts/seed_dev_admins.py

Idempotent: re-running it preserves existing accounts (passwords stay the same).
"""
import asyncio
import os
import secrets
import string
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext

load_dotenv("/app/backend/.env")
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEVS = [
    {"first": "Benjamin",  "last": None,           "email": "benjamin@taskforce.ai"},
    {"first": "Shannon",   "last": "Lee",          "email": "shannon@taskforce.ai"},
    {"first": "Sultan",    "last": "Al Hashmi",    "email": "sultan@taskforce.ai"},
    {"first": "Salem",     "last": "Al Khammas",   "email": "salem@taskforce.ai"},
    {"first": "Anton",     "last": "Glotser",      "email": "anton@taskforce.ai"},
    {"first": "Ian",       "last": "Conner",       "email": "ian@taskforce.ai"},
    {"first": "Justin",    "last": None,           "email": "justin@taskforce.ai"},
]


def gen_password(first_name: str) -> str:
    """firstname-XXXXXXXX format — alphanumeric, 8-char random suffix.
    Mixed case + digits for ~47 bits of entropy on the suffix alone."""
    alphabet = string.ascii_letters + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"{first_name.lower()}-{suffix}"


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc).isoformat()

    # 1) Mark admin@nova.ai as the owner.
    owner = await db.users.find_one({"email": "admin@nova.ai"})
    if owner:
        await db.users.update_one(
            {"email": "admin@nova.ai"},
            {"$set": {"is_owner": True, "tier": "owner"}},
        )
        print("✅ admin@nova.ai → owner (is_owner=true, tier=owner)")
    else:
        print("⚠️  admin@nova.ai not found — skipping owner stamp")

    # 2) Create / refresh the 7 dev admins.
    print("\n📋 Dev admin credentials:")
    print("=" * 70)
    out_lines = []
    for d in DEVS:
        full_name = f"{d['first']}" + (f" {d['last']}" if d['last'] else "")
        existing = await db.users.find_one({"email": d["email"]})
        if existing:
            # Don't rotate existing password silently. Print a notice.
            print(f"   {full_name:25} {d['email']:30} (already exists — password unchanged)")
            out_lines.append((full_name, d["email"], "<unchanged — see prior issue of this file>"))
            # Ensure their role+is_owner reflect current policy:
            await db.users.update_one(
                {"email": d["email"]},
                {"$set": {"role": "admin", "is_owner": False, "tier": "dev"}},
            )
            continue

        password = gen_password(d["first"])
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": d["email"],
            "password_hash": pwd_ctx.hash(password),
            "name": full_name,
            "role": "admin",
            "is_owner": False,
            "tier": "dev",
            "created_at": now,
        })
        print(f"   {full_name:25} {d['email']:30} {password}")
        out_lines.append((full_name, d["email"], password))

    print("=" * 70)
    print("\n⚠️  Save these passwords now — they're hashed in the DB after this.")
    print("\nLogins are role=admin (full admin access) but is_owner=false (owner-")
    print("gated routes like security panels remain restricted to admin@nova.ai).")

    # Write a sibling text file with the generated rows for the dev to paste into Slack/email.
    out_path = "/app/memory/_dev_admins_provisioned.md"
    with open(out_path, "w") as f:
        f.write("# Dev Admins Provisioned\n\n")
        f.write(f"_Generated {now}_\n\n")
        f.write("| Name | Email | Password | Role | Owner? |\n")
        f.write("|------|-------|----------|------|--------|\n")
        for name, email, pwd in out_lines:
            f.write(f"| {name} | `{email}` | `{pwd}` | admin | ❌ |\n")
        f.write(f"| Task Force Admin | `admin@nova.ai` | `admin123` (existing) | admin | ✅ owner |\n")
        f.write("\n**Notes:**\n")
        f.write("- `is_owner` field added to all users (default `false`).\n")
        f.write("- `tier` field set to `dev` for the 7 above; `owner` for `admin@nova.ai`.\n")
        f.write("- All 7 devs pass every existing `role == 'admin'` gate. The platform-owner\n")
        f.write("  reserves `is_owner == true` for future security/secrets routes.\n")
    print(f"\n📄 Wrote {out_path}")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
