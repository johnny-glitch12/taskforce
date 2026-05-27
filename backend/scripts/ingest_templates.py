"""
Ingest n8n templates from GitHub → Task Force AI native schema.

Crawls https://github.com/enescingoz/awesome-n8n-templates, downloads
each workflow JSON, translates via lib/n8n_translator, and upserts
into MongoDB `n8n_templates` collection.

Usage:
    python scripts/ingest_templates.py --limit 20
    python scripts/ingest_templates.py --all
"""
import os
import sys
import json
import argparse
import asyncio
from datetime import datetime, timezone
from pathlib import Path

# Allow imports from /app/backend
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

from lib.n8n_translator import translate_workflow

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

GITHUB_API = "https://api.github.com"
REPO_OWNER = "enescingoz"
REPO_NAME = "awesome-n8n-templates"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main"

# Curated top 20 templates (high-value, broad coverage)
CURATED = [
    "Gmail_and_Email_Automation",
    "Telegram",
    "Notion_and_Knowledge_Management",
    "AI_Research_RAG_and_Data_Analysis",
    "OpenAI_and_LLMs",
    "Slack",
    "Discord",
    "WhatsApp",
    "WordPress",
    "Database_and_Storage",
    "Forms_and_Surveys",
    "Other_Integrations_and_Use_Cases",
    "PDF_and_Document_Processing",
    "Social_Media",
    "YouTube",
    "Instagram_Twitter_Social",
    "Airtable",
    "Google_Drive_and_Google_Sheets",
    "HR_and_Recruitment",
    "Calendar_and_Scheduling_Tasks",
]


async def list_workflow_files(client: httpx.AsyncClient, limit: int = 20) -> list:
    """List .json workflow files in the repo via GitHub Trees API (recursive)."""
    print(f"[ingest] Fetching repo tree from {REPO_OWNER}/{REPO_NAME}...")
    headers = {}
    gh_token = os.environ.get("GITHUB_TOKEN")
    if gh_token:
        headers["Authorization"] = f"Bearer {gh_token}"

    # Get default branch
    res = await client.get(
        f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}",
        headers=headers, timeout=30,
    )
    if res.status_code != 200:
        print(f"[ingest] Failed to fetch repo metadata: {res.status_code}")
        return []
    default_branch = res.json().get("default_branch", "main")

    # Get tree
    res = await client.get(
        f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/git/trees/{default_branch}?recursive=1",
        headers=headers, timeout=30,
    )
    if res.status_code != 200:
        print(f"[ingest] Failed to fetch tree: {res.status_code}")
        return []

    tree = res.json().get("tree", [])
    all_json = [
        t["path"] for t in tree
        if t.get("type") == "blob" and t.get("path", "").endswith(".json")
    ]
    print(f"[ingest] Found {len(all_json)} JSON files total.")

    # Sort: curated category files first, then by simplest path
    def priority(path: str) -> int:
        for i, cat in enumerate(CURATED):
            if path.startswith(cat):
                return i
        return 1000

    all_json.sort(key=lambda p: (priority(p), len(p)))
    return all_json[:limit]


async def download_and_parse(client: httpx.AsyncClient, path: str) -> dict | None:
    """Download a workflow JSON and translate it."""
    url = f"{RAW_BASE}/{path}"
    try:
        res = await client.get(url, timeout=30)
        if res.status_code != 200:
            print(f"  [skip] {path} (HTTP {res.status_code})")
            return None
        n8n_json = res.json()
        if not isinstance(n8n_json, dict) or "nodes" not in n8n_json:
            print(f"  [skip] {path} (not a workflow)")
            return None
        # Derive category from folder
        category = path.split("/")[0].replace("_", " ").strip() if "/" in path else "General"
        translated = translate_workflow(n8n_json, source_path=path)
        translated["category"] = category
        return translated
    except Exception as e:
        print(f"  [error] {path}: {e}")
        return None


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20, help="Max templates to ingest")
    parser.add_argument("--all", action="store_true", help="Ingest all available")
    parser.add_argument("--local-dir", type=str, default="", help="Use a local clone instead of GitHub API")
    args = parser.parse_args()

    limit = 10000 if args.all else args.limit

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        print("[ingest] MONGO_URL or DB_NAME not set in .env")
        return

    mongo = AsyncIOMotorClient(mongo_url)
    db = mongo[db_name]

    if args.local_dir:
        await _ingest_local(db, args.local_dir, limit)
    else:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            paths = await list_workflow_files(client, limit=limit)
            print(f"[ingest] Processing {len(paths)} workflows...")

            ingested = 0
            for path in paths:
                translated = await download_and_parse(client, path)
                if not translated:
                    continue

                now = datetime.now(timezone.utc).isoformat()
                translated["updated_at"] = now

                await db.n8n_templates.update_one(
                    {"source_hash": translated["source_hash"]},
                    {
                        "$set": translated,
                        "$setOnInsert": {"created_at": now, "id": translated["source_hash"]},
                    },
                    upsert=True,
                )
                ingested += 1
                print(f"  [ok] {translated['name']} ({translated['node_count']} nodes, {translated['category']})")

            # Indexes
            await db.n8n_templates.create_index("source_hash", unique=True)
            await db.n8n_templates.create_index("category")
            await db.n8n_templates.create_index("node_count")

            print(f"\n[ingest] DONE — {ingested} templates ingested.")

    mongo.close()


async def _ingest_local(db, root_dir: str, limit: int):
    """Walk a local clone of the repo and translate each JSON workflow."""
    from lib.n8n_translator import translate_workflow as _tx
    root = Path(root_dir)
    if not root.exists():
        print(f"[ingest] local dir not found: {root_dir}")
        return

    # Group files by category, then round-robin pick
    by_cat: dict = {}
    for p in root.rglob("*.json"):
        if p.is_file():
            by_cat.setdefault(p.parent.name, []).append(p)

    # Curated categories first
    ordered_cats = [c for c in CURATED if c in by_cat] + [c for c in by_cat if c not in CURATED]

    # Round-robin pick from each category until we hit limit
    picked = []
    rr_idx = 0
    cat_pointers = {c: 0 for c in ordered_cats}
    while len(picked) < limit and any(cat_pointers[c] < len(by_cat[c]) for c in ordered_cats):
        cat = ordered_cats[rr_idx % len(ordered_cats)]
        files = by_cat[cat]
        if cat_pointers[cat] < len(files):
            picked.append(files[cat_pointers[cat]])
            cat_pointers[cat] += 1
        rr_idx += 1

    print(f"[ingest] Local clone: {sum(len(v) for v in by_cat.values())} JSON files, {len(by_cat)} categories.")
    print(f"[ingest] Processing {len(picked)} workflows (round-robin across categories, limit={limit})...")

    ingested = 0
    skipped = 0
    for f in picked:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                n8n_json = json.load(fp)
        except Exception as e:
            skipped += 1
            print(f"  [skip] {f.name} (parse error: {e})")
            continue

        if not isinstance(n8n_json, dict) or "nodes" not in n8n_json:
            skipped += 1
            continue

        # Use filename as fallback for "Untitled" workflows
        if not n8n_json.get("name") or n8n_json["name"].strip().lower() in ("untitled workflow", "my workflow", ""):
            n8n_json["name"] = f.stem.replace("_", " ").strip()

        rel = str(f.relative_to(root))
        category = f.parent.name.replace("_", " ").strip()
        try:
            translated = _tx(n8n_json, source_path=rel)
        except Exception as e:
            skipped += 1
            print(f"  [skip] {f.name} (translate error: {e})")
            continue

        translated["category"] = category
        now = datetime.now(timezone.utc).isoformat()
        translated["updated_at"] = now

        await db.n8n_templates.update_one(
            {"source_hash": translated["source_hash"]},
            {
                "$set": translated,
                "$setOnInsert": {"created_at": now, "id": translated["source_hash"]},
            },
            upsert=True,
        )
        ingested += 1
        print(f"  [ok] {translated['name']} ({translated['node_count']} nodes, {category})")

    await db.n8n_templates.create_index("source_hash", unique=True)
    await db.n8n_templates.create_index("category")
    await db.n8n_templates.create_index("node_count")
    print(f"\n[ingest] DONE — {ingested} ingested, {skipped} skipped.")


if __name__ == "__main__":
    asyncio.run(main())
