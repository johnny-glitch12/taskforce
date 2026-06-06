"""
migrate_listings_to_credits.py — one-shot backfill for Prompt 21 / iter61.

The Exchange has moved to credit-only purchases. Pre-existing listings created
under the legacy `rent_price` / `buy_price` (USD) model still have
`price_credits = 0` which causes the new UI to display them as "FREE".

This script backfills `price_credits` for every listing where:
  - `price_credits` is missing OR equal to 0, AND
  - `rent_price > 0` OR `buy_price > 0`

Conversion rule:
  price_credits = round( max(buy_price, rent_price * 5) * 100 )
  (rent is per-run, so we anchor on a multiplier of 5 runs to approximate
   one-time value; otherwise we'd undervalue rent-only listings.)

Capped at 10000 to fit the schema bound.

Idempotent — only touches rows where `price_credits` is currently 0.

Run:
  python -m backend.scripts.migrate_listings_to_credits           # dry-run
  python -m backend.scripts.migrate_listings_to_credits --apply   # write
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Allow running as plain script: `python backend/scripts/migrate_listings_to_credits.py`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from motor.motor_asyncio import AsyncIOMotorClient


def compute_credits(listing: dict) -> int:
    rent = float(listing.get("rent_price") or 0)
    buy = float(listing.get("buy_price") or 0)
    anchor_usd = max(buy, rent * 5)
    credits = round(anchor_usd * 100)
    return min(credits, 10_000)


async def main(apply: bool) -> None:
    # Load backend/.env so MONGO_URL / DB_NAME are available when run as a script.
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    except ImportError:
        pass
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        raise SystemExit("MONGO_URL / DB_NAME missing.")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    cursor = db.exchange_listings.find({
        "$and": [
            {"$or": [{"price_credits": {"$exists": False}}, {"price_credits": 0}, {"price_credits": None}]},
            {"$or": [{"rent_price": {"$gt": 0}}, {"buy_price": {"$gt": 0}}]},
        ]
    })

    touched = 0
    skipped_zero = 0
    plan = []
    async for listing in cursor:
        credits = compute_credits(listing)
        if credits <= 0:
            skipped_zero += 1
            continue
        plan.append((listing["id"], listing.get("name", "?"), credits, listing.get("rent_price", 0), listing.get("buy_price", 0)))

    print(f"\nFound {len(plan)} listings to migrate ({skipped_zero} skipped — zero-priced).")
    print("-" * 88)
    print(f"{'ID':<24} {'NAME':<30} {'CREDITS':>9}  rent$ → buy$")
    print("-" * 88)
    for lid, name, credits, rent, buy in plan:
        print(f"{lid[:24]:<24} {(name or '')[:30]:<30} {credits:>9}  {rent:>5} → {buy}")
    print("-" * 88)

    if not apply:
        print("\nDry-run only. Pass --apply to write changes.")
        return

    for lid, _name, credits, _r, _b in plan:
        result = await db.exchange_listings.update_one(
            {"id": lid, "$or": [{"price_credits": {"$exists": False}}, {"price_credits": 0}, {"price_credits": None}]},
            {"$set": {"price_credits": int(credits)}},
        )
        if result.modified_count:
            touched += 1

    print(f"\n✓ Migrated {touched} listings to credit pricing.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="actually write the changes")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
