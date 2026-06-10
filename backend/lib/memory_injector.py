"""
Memory injector — Task Force AI (Phase 2)

Turns the user's profile + accumulated memories into a single markdown block
ready for system-prompt injection. Pure function — NO db reads, NO writes,
NO side effects, deterministic for a given input.

Design choices:
  - Corrections always survive the token budget; they are the highest-priority
    signal ("don't repeat the same mistake"). If the budget is exceeded we drop
    the OLDEST non-correction memories first.
  - Token budget is approximated as ~4 chars/token, capped at ~2000 tokens =
    ~8000 chars total block size. This is a soft cap — we don't truncate mid
    bullet, we drop whole memories.
  - Empty-input safety: returns an empty string when nothing is worth saying,
    so the caller can simply prepend the result (empty prefix is a no-op).
"""
from typing import Any, Optional

_MAX_MEMORIES = 50
_CHAR_BUDGET = 8000

# Render order for the typed-memories section (corrections handled separately)
_RENDER_ORDER = ("preference", "business_context", "technical", "feedback")

_FOOTER_HINT = (
    "Use this context to apply preferences without asking and avoid past corrections. "
    "Do NOT mention this memory system explicitly."
)


def build_memory_context(profile: Optional[dict], memories: Optional[list[dict]]) -> str:
    """Return the markdown block to prepend to the system prompt.
    Empty string when both inputs are empty/null."""
    profile = profile or {}
    memories = [m for m in (memories or []) if isinstance(m, dict)]

    business = profile.get("business") or {}
    preferences = profile.get("preferences") or {}
    integrations = profile.get("integrations") or {}

    has_profile = any([_section_has_content(business),
                       _section_has_content(preferences),
                       _integrations_has_content(integrations)])
    has_memories = bool(memories)

    if not has_profile and not has_memories:
        return ""

    # Split memories
    corrections = [m for m in memories if m.get("type") == "correction"]
    others = [m for m in memories if m.get("type") != "correction"]

    # Hard cap on total memories — corrections always survive
    if len(corrections) + len(others) > _MAX_MEMORIES:
        keep_others = max(0, _MAX_MEMORIES - len(corrections))
        others = _sort_by_recency_desc(others)[:keep_others]
    else:
        others = _sort_by_recency_desc(others)

    # Bucket others by type for rendering
    by_type: dict[str, list[dict]] = {t: [] for t in _RENDER_ORDER}
    for m in others:
        t = m.get("type")
        if t in by_type:
            by_type[t].append(m)

    block = _assemble(business, preferences, integrations, corrections, by_type)

    # Soft token-budget enforcement: drop oldest non-correction bullets until
    # the block fits. Re-assemble between drops so the rendered length is real.
    while len(block) > _CHAR_BUDGET and _has_droppable(by_type):
        _drop_oldest_non_correction(by_type)
        block = _assemble(business, preferences, integrations, corrections, by_type)

    return block


# ─── Internals ──────────────────────────────────────────────────
def _section_has_content(d: Any) -> bool:
    if not isinstance(d, dict):
        return False
    for v in d.values():
        if v is None or v == "" or v == [] or v == {} or v is False:
            continue
        return True
    return False


def _integrations_has_content(d: Any) -> bool:
    if not isinstance(d, dict):
        return False
    if isinstance(d.get("byok_keys"), list) and d["byok_keys"]:
        return True
    for k, v in d.items():
        if k == "byok_keys":
            continue
        if v is True:
            return True
    return False


def _sort_by_recency_desc(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: r.get("created_at") or "", reverse=True)


def _has_droppable(by_type: dict[str, list[dict]]) -> bool:
    return any(len(v) > 0 for v in by_type.values())


def _drop_oldest_non_correction(by_type: dict[str, list[dict]]) -> None:
    """Find the bucket with the oldest entry and pop it from there."""
    oldest_bucket = None
    oldest_ts = "ÿ"  # higher than any ISO timestamp
    for t, rows in by_type.items():
        if not rows:
            continue
        # rows are sorted desc by created_at; the last row is the oldest
        last_ts = rows[-1].get("created_at") or ""
        if last_ts < oldest_ts:
            oldest_ts = last_ts
            oldest_bucket = t
    if oldest_bucket is not None and by_type[oldest_bucket]:
        by_type[oldest_bucket].pop()


def _bullet(line: str) -> str:
    return f"- {line.strip()}"


def _kv_bullets(d: dict) -> list[str]:
    out = []
    if not isinstance(d, dict):
        return out
    for k, v in d.items():
        if v is None or v == "" or v == [] or v == {} or v is False:
            continue
        if isinstance(v, bool):
            out.append(_bullet(f"{k.replace('_', ' ')}: yes"))
        elif isinstance(v, (int, float, str)):
            out.append(_bullet(f"{k.replace('_', ' ')}: {v}"))
        elif isinstance(v, list):
            joined = ", ".join(str(it) for it in v)
            if joined:
                out.append(_bullet(f"{k.replace('_', ' ')}: {joined}"))
        elif isinstance(v, dict):
            sub = _kv_bullets(v)
            if sub:
                out.append(_bullet(f"{k.replace('_', ' ')}:"))
                out.extend("  " + s for s in sub)
    return out


def _integrations_bullets(d: dict) -> list[str]:
    out = []
    if not isinstance(d, dict):
        return out
    bks = d.get("byok_keys") if isinstance(d.get("byok_keys"), list) else []
    for slug in bks:
        out.append(_bullet(f"{slug} — BYOK key configured (key value not exposed)"))
    for k, v in d.items():
        if k == "byok_keys":
            continue
        if v is True:
            out.append(_bullet(f"{k.replace('_', ' ')} — active"))
    return out


def _assemble(
    business: dict, preferences: dict, integrations: dict,
    corrections: list[dict], by_type: dict[str, list[dict]],
) -> str:
    lines: list[str] = []
    lines.append("=== USER CONTEXT (from previous sessions) ===")
    lines.append("")

    bb = _kv_bullets(business)
    if bb:
        lines.append("## Business")
        lines.extend(bb)
        lines.append("")

    pb = _kv_bullets(preferences)
    if pb:
        lines.append("## Preferences")
        lines.extend(pb)
        lines.append("")

    ib = _integrations_bullets(integrations)
    if ib:
        lines.append("## Integrations (capabilities only — NO key values)")
        lines.extend(ib)
        lines.append("")

    if corrections:
        lines.append("## Corrections (highest priority — never contradict these)")
        for c in corrections:
            lines.append(_bullet(c.get("content", "")))
        lines.append("")

    # Memory bullets grouped by type
    if any(by_type.values()):
        lines.append("## Prior Memories")
        for t in _RENDER_ORDER:
            for m in by_type.get(t, []):
                lines.append(_bullet(f"[{t}] {m.get('content', '')}"))
        lines.append("")

    lines.append(_FOOTER_HINT)
    return "\n".join(lines).strip() + "\n"


__all__ = ["build_memory_context"]
