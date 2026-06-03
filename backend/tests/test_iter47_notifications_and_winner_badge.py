"""
Iter47 — Notifications bell + Bounty Winner badge polish.

Validates:
  GET   /api/notifications              (list, unread count, sort newest first)
  GET   /api/notifications/unread-count (lightweight badge endpoint)
  POST  /api/notifications/{id}/read    (per-row)
  POST  /api/notifications/mark-all-read (bulk)
  - 404 on read of someone else's notification
  - Exchange listing acquires bounty_winner=true + bounty_winner_title after award
"""
import asyncio
import io
import json
import os
import sys
import time
import uuid
import zipfile
from datetime import datetime, timezone

import pytest
import requests

sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@nova.ai"
ADMIN_PASS = "admin123"
USER_EMAIL = "freeuser@test.com"
USER_PASS = "test123"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=15)
    return r.json().get("token") if r.status_code == 200 else None


def _run(coro_factory):
    import asyncio as _aio
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")

    async def _main():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            db = client[os.environ["DB_NAME"]]
            return await coro_factory(db)
        finally:
            client.close()
    return _aio.run(_main())


@pytest.fixture(scope="module")
def admin_auth():
    t = _login(ADMIN_EMAIL, ADMIN_PASS)
    assert t
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="module")
def user_auth():
    t = _login(USER_EMAIL, USER_PASS)
    assert t
    return {"Authorization": f"Bearer {t}"}


def _ensure_user_has_credits(email: str, amount: int = 5000):
    _run(lambda db: db.users.update_one(
        {"email": email}, {"$set": {"topup_credits": amount}}, upsert=False,
    ))


def _clear_notifications_for(email: str):
    """Wipe all notifications addressed to a user (across both id + email fallbacks)."""
    async def _flow(db):
        u = await db.users.find_one({"email": email}, {"id": 1})
        ids = [email]
        if u and u.get("id"):
            ids.append(u["id"])
        await db.notifications.delete_many({"user_id": {"$in": ids}})
    _run(_flow)


def _create_bounty(headers, *, reward=200, deadline_days=5):
    body = {
        "title": f"Iter47 notif test {uuid.uuid4().hex[:6]}",
        "description": "Notification test bounty — minimum 20 chars satisfied.",
        "category": "automation",
        "reward_amount": reward,
        "deadline_days": deadline_days,
    }
    r = requests.post(f"{BASE_URL}/api/bounties", headers=headers, json=body, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["bounty"]


def _create_external_pkg(headers, name_prefix="iter47") -> str:
    manifest = {
        "name": f"{name_prefix}-{uuid.uuid4().hex[:6]}",
        "version": "1.0.0",
        "display_name": "Iter47 submission target",
        "description": "Notification + winner-badge target.",
        "runtime": "python3.11",
        "entry_point": "main.py",
        "entry_function": "run",
        "dependencies": [],
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest))
        z.writestr("main.py", "def run(input):\n    return {'ok': True}\n")
    r = requests.post(
        f"{BASE_URL}/api/external-agents/upload",
        headers=headers,
        files={"file": (f"{manifest['name']}.tfagent", buf.getvalue(), "application/zip")},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    return r.json()["package_id"]


# ── Notifications tests ─────────────────────────────────────────────────────
def test_unread_count_lightweight_endpoint(user_auth):
    """The /unread-count endpoint must return JUST a count, no payload."""
    r = requests.get(f"{BASE_URL}/api/notifications/unread-count",
                     headers=user_auth, timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "unread" in body
    assert isinstance(body["unread"], int)
    assert "items" not in body


def test_list_returns_items_and_unread(user_auth):
    r = requests.get(f"{BASE_URL}/api/notifications?limit=20",
                     headers=user_auth, timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "unread" in body


def test_notifications_fire_on_submit_and_award(user_auth, admin_auth):
    """Wire a fresh bounty + submission + award through and assert notifications
    land for both the poster and the winner."""
    _ensure_user_has_credits(USER_EMAIL, 5000)
    # Clean slate.
    _clear_notifications_for(USER_EMAIL)
    _clear_notifications_for(ADMIN_EMAIL)

    b = _create_bounty(user_auth, reward=200)
    pkg_id = _create_external_pkg(admin_auth, name_prefix="notif")
    sub_r = requests.post(
        f"{BASE_URL}/api/bounties/{b['id']}/submit", headers=admin_auth,
        json={"agent_source": "external", "source_id": pkg_id,
              "pitch": "I built this exact thing already. " * 3}, timeout=15,
    )
    assert sub_r.status_code == 200
    sub_id = sub_r.json()["submission"]["id"]

    # Small wait for fire-and-forget task to land in mongo.
    time.sleep(0.5)

    # Poster should see a `bounty_submission_new` notification.
    poster_n = requests.get(
        f"{BASE_URL}/api/notifications?limit=10", headers=user_auth, timeout=10,
    ).json()
    submission_notif = next(
        (n for n in poster_n["items"] if n["kind"] == "bounty_submission_new"),
        None,
    )
    assert submission_notif is not None, "poster should be notified of new submissions"
    assert submission_notif["payload"]["bounty_id"] == b["id"]

    # Award + verify winner gets bounty_won.
    award_r = requests.post(
        f"{BASE_URL}/api/bounties/{b['id']}/award", headers=user_auth,
        json={"submission_id": sub_id}, timeout=15,
    )
    assert award_r.status_code == 200
    time.sleep(0.5)
    winner_n = requests.get(
        f"{BASE_URL}/api/notifications?limit=10", headers=admin_auth, timeout=10,
    ).json()
    won = next((n for n in winner_n["items"] if n["kind"] == "bounty_won"), None)
    assert won is not None, "winner should be notified"
    assert won["payload"]["bounty_id"] == b["id"]
    assert won["payload"]["reward"] == 200

    # Cleanup
    requests.delete(f"{BASE_URL}/api/external-agents/packages/{pkg_id}",
                    headers=admin_auth, timeout=10)


def test_mark_read_and_mark_all(user_auth):
    """Mark one as read, then mark all — unread count goes to 0."""
    _ensure_user_has_credits(USER_EMAIL, 5000)
    _clear_notifications_for(USER_EMAIL)
    # Seed a notification by submitting to a bounty.
    b = _create_bounty(user_auth, reward=200)
    # User submits a sibling submission via admin to trigger the poster notif.
    admin_t = _login(ADMIN_EMAIL, ADMIN_PASS)
    admin_h = {"Authorization": f"Bearer {admin_t}"}
    pkg = _create_external_pkg(admin_h, name_prefix="markread")
    requests.post(f"{BASE_URL}/api/bounties/{b['id']}/submit", headers=admin_h,
                  json={"agent_source": "external", "source_id": pkg,
                        "pitch": "Pitch text valid for tests. " * 3}, timeout=15)
    time.sleep(0.5)

    # Now there should be at least 1 unread.
    pre = requests.get(f"{BASE_URL}/api/notifications/unread-count",
                       headers=user_auth, timeout=10).json()
    assert pre["unread"] >= 1
    # Fetch + mark first one read.
    listing = requests.get(f"{BASE_URL}/api/notifications?limit=1",
                           headers=user_auth, timeout=10).json()
    first_id = listing["items"][0]["id"]
    r_one = requests.post(f"{BASE_URL}/api/notifications/{first_id}/read",
                          headers=user_auth, timeout=10)
    assert r_one.status_code == 200
    mid = requests.get(f"{BASE_URL}/api/notifications/unread-count",
                       headers=user_auth, timeout=10).json()
    assert mid["unread"] == pre["unread"] - 1
    # Mark all.
    r_all = requests.post(f"{BASE_URL}/api/notifications/mark-all-read",
                          headers=user_auth, timeout=10)
    assert r_all.status_code == 200
    after = requests.get(f"{BASE_URL}/api/notifications/unread-count",
                         headers=user_auth, timeout=10).json()
    assert after["unread"] == 0
    # Cleanup
    requests.delete(f"{BASE_URL}/api/external-agents/packages/{pkg}",
                    headers=admin_h, timeout=10)


def test_cannot_mark_someone_elses_notification(user_auth, admin_auth):
    """Trying to mark another user's notification returns 404."""
    # Get one of admin's notifications.
    a = requests.get(f"{BASE_URL}/api/notifications?limit=1",
                     headers=admin_auth, timeout=10).json()
    if not a["items"]:
        pytest.skip("no admin notifications to test cross-user access against")
    foreign_id = a["items"][0]["id"]
    r = requests.post(f"{BASE_URL}/api/notifications/{foreign_id}/read",
                      headers=user_auth, timeout=10)
    assert r.status_code == 404


def test_unread_only_filter(user_auth):
    """unread_only=true returns only unread rows."""
    _clear_notifications_for(USER_EMAIL)
    # Seed two notifications via two submissions to two different bounties.
    admin_t = _login(ADMIN_EMAIL, ADMIN_PASS)
    admin_h = {"Authorization": f"Bearer {admin_t}"}
    _ensure_user_has_credits(USER_EMAIL, 5000)
    b1 = _create_bounty(user_auth, reward=200)
    b2 = _create_bounty(user_auth, reward=200)
    p1 = _create_external_pkg(admin_h, name_prefix="filter-a")
    p2 = _create_external_pkg(admin_h, name_prefix="filter-b")
    requests.post(f"{BASE_URL}/api/bounties/{b1['id']}/submit", headers=admin_h,
                  json={"agent_source": "external", "source_id": p1,
                        "pitch": "Pitch A long enough to validate. " * 3}, timeout=15)
    requests.post(f"{BASE_URL}/api/bounties/{b2['id']}/submit", headers=admin_h,
                  json={"agent_source": "external", "source_id": p2,
                        "pitch": "Pitch B long enough to validate. " * 3}, timeout=15)
    time.sleep(0.5)
    listing = requests.get(f"{BASE_URL}/api/notifications?limit=20",
                           headers=user_auth, timeout=10).json()
    assert listing["unread"] >= 2
    # Mark one read.
    target = listing["items"][0]["id"]
    requests.post(f"{BASE_URL}/api/notifications/{target}/read",
                  headers=user_auth, timeout=10)
    only_unread = requests.get(
        f"{BASE_URL}/api/notifications?unread_only=true&limit=20",
        headers=user_auth, timeout=10,
    ).json()
    assert all(not n["read"] for n in only_unread["items"])
    assert target not in {n["id"] for n in only_unread["items"]}
    # Cleanup
    for p in (p1, p2):
        requests.delete(f"{BASE_URL}/api/external-agents/packages/{p}",
                        headers=admin_h, timeout=10)


# ── Bounty Winner badge on Exchange listing ───────────────────────────────
def _create_published_listing(headers) -> str:
    """Create a fresh draft listing then mark it published via the direct route."""
    body = {
        "name": f"iter47-listing-{uuid.uuid4().hex[:6]}",
        "description": "Iter47 listing for bounty-winner badge test.",
        "category": "automation",
        "tags": ["test"],
        "rent_price": 1.0,
        "buy_price": 5.0,
        "avatar_icon": "trophy",
        "avatar_color": "#fbbf24",
        "required_integrations": [],
        "trigger_type": "manual",
        "engine": "gemini-flash",
        "files": [{"path": "main.py", "language": "python",
                   "content": "def run(input):\n    return {'ok': True}\n"}],
        "nodes": [{"id": "n1", "type": "noop"}],
        "edges": [],
        "language": "python",
    }
    r = requests.post(f"{BASE_URL}/api/exchange/listings/direct",
                      headers=headers, json=body, timeout=15)
    assert r.status_code == 200, r.text
    listing_id = r.json()["id"]
    # Mark published (admin bypasses hosting quota).
    r2 = requests.put(f"{BASE_URL}/api/exchange/listings/{listing_id}",
                      headers=headers, json={"status": "published"}, timeout=10)
    assert r2.status_code == 200, r2.text
    return listing_id


def test_winning_exchange_listing_gets_bounty_winner_badge(user_auth, admin_auth):
    """Award a bounty to a SUBMISSION whose agent_source='exchange' — the
    underlying listing must acquire bounty_winner=true + title + id + wins counter."""
    _ensure_user_has_credits(USER_EMAIL, 5000)
    listing_id = _create_published_listing(admin_auth)
    b = _create_bounty(user_auth, reward=200)
    # Admin submits the listing.
    sub_r = requests.post(
        f"{BASE_URL}/api/bounties/{b['id']}/submit", headers=admin_auth,
        json={"agent_source": "exchange", "source_id": listing_id,
              "pitch": "Exchange-published listing submitted to bounty. " * 2}, timeout=15,
    )
    assert sub_r.status_code == 200, sub_r.text
    sub_id = sub_r.json()["submission"]["id"]
    award_r = requests.post(
        f"{BASE_URL}/api/bounties/{b['id']}/award", headers=user_auth,
        json={"submission_id": sub_id}, timeout=15,
    )
    assert award_r.status_code == 200
    assert award_r.json()["winner_listing_id"] == listing_id

    # Listing now carries the badge.
    listing = _run(lambda db: db.exchange_listings.find_one({"id": listing_id}))
    assert listing["bounty_winner"] is True
    assert listing["bounty_winner_id"] == b["id"]
    assert listing["bounty_winner_title"] == b["title"]
    assert (listing.get("bounty_wins") or 0) >= 1

    # Public listings endpoint surfaces those fields too.
    pub = requests.get(f"{BASE_URL}/api/exchange/listings?limit=100", timeout=10).json()
    target = next((x for x in pub["listings"] if x["id"] == listing_id), None)
    assert target is not None
    assert target.get("bounty_winner") is True
    assert target.get("bounty_winner_title") == b["title"]

    # Cleanup
    requests.delete(f"{BASE_URL}/api/exchange/listings/{listing_id}",
                    headers=admin_auth, timeout=10)


def test_cleanup(user_auth):
    """Final-state cleanup."""
    async def _flow(db):
        await db.bounties.delete_many({"poster_email": {"$in": [ADMIN_EMAIL, USER_EMAIL]}})
        await db.bounty_submissions.delete_many(
            {"creator_email": {"$in": [ADMIN_EMAIL, USER_EMAIL]}},
        )
        await db.notifications.delete_many(
            {"user_id": {"$in": [ADMIN_EMAIL, USER_EMAIL]}},
        )
    _run(_flow)
    # No assertion needed — best-effort cleanup.
