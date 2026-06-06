"""
Regression tests for Prompt 21 work:

1. Golden examples library — keyword matching + hint formatting
2. Seed official agents — listings exist, are official, have correct shape
3. Migration script — idempotency (re-running doesn't double up)

Run:  pytest -v backend/tests/test_iter62_seed_agents.py
"""
import os
import asyncio
from pathlib import Path

import pytest


# ───────────────── Golden examples ─────────────────
def test_golden_examples_keyword_matching():
    from lib.golden_examples import pick_example, GOLDEN_EXAMPLES

    assert len(GOLDEN_EXAMPLES) >= 5, "should have at least 5 golden patterns"

    # Each pattern should match its own keyword set.
    cases = {
        "gmail_classifier":  "Read my gmail inbox and qualify leads",
        "content_repurpose": "Take a blog post and create a twitter thread",
        "stripe_billing":    "Find overdue stripe invoices and follow up",
        "meeting_notes":     "Extract action items from this meeting transcript",
        "slack_notifier":    "Post a slack notification on a webhook",
    }
    for ex_id, prompt in cases.items():
        match = pick_example(prompt)
        assert match is not None, f"no match for {prompt!r}"
        assert match["id"] == ex_id, f"expected {ex_id} for {prompt!r}, got {match['id']}"


def test_golden_examples_no_match_for_unrelated():
    from lib.golden_examples import pick_example
    # Unrelated prompts return None.
    assert pick_example("Build a chess engine that plays well") is None


def test_planner_and_builder_hints_format():
    from lib.golden_examples import planner_hint, builder_hint
    p = planner_hint("Read gmail inbox and qualify leads")
    b = builder_hint("Read gmail inbox and qualify leads")
    assert "REFERENCE EXAMPLE" in p
    assert "```json" in p
    assert "gmail_classifier" in p
    assert "REFERENCE IMPLEMENTATION" in b
    assert "```python" in b


def test_hints_empty_for_no_match():
    from lib.golden_examples import planner_hint, builder_hint
    assert planner_hint("Build a chess engine") == ""
    assert builder_hint("Build a chess engine") == ""


# ───────────────── Seed agents — DB inspection ─────────────────
@pytest.mark.asyncio
async def test_seed_agents_present_in_db():
    # Late imports so the test still runs even if module is reloaded.
    from motor.motor_asyncio import AsyncIOMotorClient
    try:
        from dotenv import load_dotenv
        load_dotenv(Path("/app/backend/.env"))
    except Exception:
        pass

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        pytest.skip("MONGO_URL/DB_NAME unavailable in test env")

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    expected_slugs = {
        "lead-responder",
        "social-media-repurposer",
        "invoice-chaser",
        "customer-support-classifier",
        "meeting-notes-action-items",
    }
    cursor = db.exchange_listings.find({"is_official": True}, {"_id": 0})
    rows = await cursor.to_list(20)
    client.close()
    found = {r["slug"] for r in rows}
    missing = expected_slugs - found
    assert not missing, f"missing official agents: {missing}"
    # Each must be 'published' and carry positive price_credits.
    for r in rows:
        assert r["status"] == "published", f"{r['slug']} not published"
        assert r.get("price_credits", 0) >= 15, f"{r['slug']} price too low: {r.get('price_credits')}"
        assert r.get("source_project_id"), f"{r['slug']} missing source_project_id"
        assert r.get("category"), f"{r['slug']} missing category"


@pytest.mark.asyncio
async def test_seed_agents_have_bot_projects_with_files_and_ui():
    from motor.motor_asyncio import AsyncIOMotorClient
    try:
        from dotenv import load_dotenv
        load_dotenv(Path("/app/backend/.env"))
    except Exception:
        pass

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        pytest.skip("MONGO_URL/DB_NAME unavailable")

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    listings = await db.exchange_listings.find({"is_official": True}).to_list(10)
    for lst in listings:
        proj = await db.bot_projects.find_one({"id": lst["source_project_id"]})
        assert proj, f"bot_project missing for {lst['slug']}"
        files = proj.get("files", [])
        names = {f["path"] for f in files}
        # Must include the standard agent layout + a React UI file.
        assert "main.py" in names, f"{lst['slug']} missing main.py"
        assert "handlers.py" in names, f"{lst['slug']} missing handlers.py"
        assert "App.jsx" in names, f"{lst['slug']} missing App.jsx UI"
        # nodes & edges sanity.
        assert proj.get("nodes"), f"{lst['slug']} has no nodes"
        assert proj.get("edges"), f"{lst['slug']} has no edges"
        # main.py must implement run(input, env, keys)
        main_py = next((f for f in files if f["path"] == "main.py"), None)
        assert main_py and "def run(" in main_py["content"], f"{lst['slug']} main.py missing run()"

    client.close()


# ───────────────── Migration script — idempotency ─────────────────
@pytest.mark.asyncio
async def test_migration_is_idempotent():
    """Running the migrate_listings_to_credits script a second time should
    not modify any listings (because all rows already have price_credits>0)."""
    import subprocess
    # First apply (no-op if already done).
    subprocess.run(["python", "/app/backend/scripts/migrate_listings_to_credits.py", "--apply"],
                   capture_output=True, check=True)
    # Second apply.
    r = subprocess.run(["python", "/app/backend/scripts/migrate_listings_to_credits.py", "--apply"],
                       capture_output=True, check=True, text=True)
    # When nothing remains to migrate, output reads "Found 0 listings".
    assert "Found 0 listings to migrate" in (r.stdout + r.stderr), \
        f"migration not idempotent. stdout:\n{r.stdout}\nstderr:\n{r.stderr}"
