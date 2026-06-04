"""
code_gen_pipeline — 5-stage Emergent-quality code generation orchestrator.

Stages: Architect → Planner → Builder → Reviewer → Polisher (→ UIBuilder if has_ui).

Design decisions:
- Cheap stages (Architect, Planner, Reviewer, Polisher) run on `gemini-2.5-flash` to
  keep platform margins healthy. Builder + UIBuilder run on the user's chosen model.
- Each stage debits credits POST-call via lib.smart_credits.debit_actual_usage so a
  failed LLM call doesn't burn the user's wallet.
- Mid-pipeline insolvency → status='paused', resumable via run_build_pipeline(resume=True).
- All progress (stage statuses, partial outputs) is persisted to `vibe_sessions.build_progress`
  so the frontend can poll /api/vibe/build-status/{session_id} and resume after a top-up.
- Builder output is AST-validated (compile + import resolution) before going to Reviewer.
  When AST is clean, Reviewer is SKIPPED (saves a credit + 5-15s latency).
"""
from __future__ import annotations

import ast
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from lib.llm_client import call_llm
from lib.smart_credits import check_can_afford, debit_actual_usage
from prompts.code_gen_prompts import (
    ARCHITECT_PROMPT,
    BUILDER_PROMPT,
    PLANNER_PROMPT,
    POLISHER_PROMPT,
    REVIEWER_PROMPT,
    UI_BUILDER_PROMPT,
)

logger = logging.getLogger("code_gen_pipeline")

# Cheap default for non-builder stages — flips ALL non-builder LLM calls to Flash
# regardless of the user's picked model. Saves ~80% on those stages with negligible
# quality impact (planning + reviewing don't need flagship reasoning).
CHEAP_STAGE_MODEL = "gemini-2.5-flash"


# ─── JSON extraction (same balanced-brace walker as vibe_coding._extract_json) ───
def _extract_json(text: str) -> dict:
    s = (text or "").strip()
    s = re.sub(r"^```(?:json|JSON)?\s*", "", s)
    s = re.sub(r"\s*```\s*$", "", s)
    start = s.find("{")
    if start < 0:
        raise ValueError("No JSON object in stage output")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return json.loads(s[start: i + 1], strict=False)
    raise ValueError("Unbalanced JSON in stage output")


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


# ─── AST validation ────────────────────────────────────
def validate_all_files(files: list) -> list[dict]:
    """Static analysis on the builder's output. Returns a list of issues for the
    Reviewer stage. Each issue: {path, line, kind, detail}.

    Checks:
    - Python syntax (ast.parse)
    - Undefined imports (top-level imports not present in requirements.txt or stdlib)
    - Missing run() function in main.py
    """
    issues: list[dict] = []
    file_map = {f["path"]: f["content"] for f in files if f.get("path")}
    stdlib = {
        "os", "sys", "json", "re", "uuid", "time", "datetime", "math", "random", "logging",
        "asyncio", "typing", "collections", "itertools", "functools", "pathlib", "hashlib",
        "base64", "subprocess", "io", "tempfile", "string", "enum", "dataclasses", "copy",
        "traceback", "inspect", "secrets", "urllib", "http", "email", "csv", "sqlite3",
        "concurrent", "threading", "multiprocessing", "socket", "ssl", "shutil",
    }
    requirements = set()
    if "requirements.txt" in file_map:
        for line in file_map["requirements.txt"].splitlines():
            pkg = line.strip().split("=")[0].split("<")[0].split(">")[0].split("[")[0].strip()
            if pkg:
                # Normalise — distribution name → import name (close enough for common cases)
                requirements.add(pkg.lower().replace("-", "_"))
    # Common alias mismatches
    requirements |= {"emergentintegrations", "anthropic", "openai", "google", "stripe"}

    # 1. Check main.py exists + has run(...)
    if "main.py" not in file_map:
        issues.append({"path": "main.py", "line": 0, "kind": "missing_file",
                       "detail": "main.py is required as the entry point."})
    else:
        try:
            tree = ast.parse(file_map["main.py"])
            has_run = any(
                isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "run"
                for n in tree.body
            )
            if not has_run:
                issues.append({"path": "main.py", "line": 0, "kind": "missing_function",
                               "detail": "main.py must define a top-level `def run(input, env=None, keys=None) -> dict` function."})
        except SyntaxError as e:
            issues.append({"path": "main.py", "line": e.lineno or 0, "kind": "syntax",
                           "detail": (e.msg or "SyntaxError")[:200]})

    # 2. AST-check every .py file for syntax + imports
    for path, content in file_map.items():
        if not path.endswith(".py"):
            continue
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            issues.append({"path": path, "line": e.lineno or 0, "kind": "syntax",
                           "detail": (e.msg or "SyntaxError")[:200]})
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = (alias.name or "").split(".")[0].lower().replace("-", "_")
                    if top and top not in stdlib and top not in requirements:
                        # Also skip "obvious" local module imports (same basename in file_map)
                        local_modules = {p.replace(".py", "") for p in file_map.keys() if p.endswith(".py")}
                        if top not in local_modules:
                            issues.append({"path": path, "line": node.lineno, "kind": "undefined_import",
                                           "detail": f"Module '{top}' is imported but not in requirements.txt or stdlib."})
            elif isinstance(node, ast.ImportFrom):
                top = (node.module or "").split(".")[0].lower().replace("-", "_") if node.module else ""
                if top and top not in stdlib and top not in requirements:
                    local_modules = {p.replace(".py", "") for p in file_map.keys() if p.endswith(".py")}
                    if top not in local_modules:
                        issues.append({"path": path, "line": node.lineno, "kind": "undefined_import",
                                       "detail": f"Module '{top}' is imported (from-import) but not in requirements.txt or stdlib."})

    # Cap at 20 issues — the reviewer prompt gets unwieldy beyond that
    return issues[:20]


# ─── Stage runner ──────────────────────────────────────
async def _run_stage(
    db,
    user: dict,
    *,
    stage: str,
    model: str,
    system_prompt: str,
    user_message: str,
    session_id: str,
    action: str = "vibe_build",
) -> dict:
    """Run a single pipeline stage. Pre-flights credits, makes the LLM call,
    debits the actual usage, and returns the parsed JSON output PLUS billing meta.

    Raises a PipelinePaused exception when the user can't afford the stage —
    the orchestrator catches it and persists status='paused' for resume."""
    pre = await check_can_afford(db, user, model, action)
    if not pre.get("allowed"):
        raise PipelinePaused(stage=stage, reason="INSUFFICIENT_CREDITS",
                             estimate=pre.get("estimated_credits", 0),
                             min_credits=pre.get("min_credits", 1))

    session_key = f"vibe-{session_id}-{stage}"
    t0 = time.time()
    result = await call_llm(
        model=model,
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": user_message}],
        session_key=session_key,
        db=db,
        user_id=str(user.get("id", user.get("email"))),
    )
    duration_ms = int((time.time() - t0) * 1000)

    parsed = _extract_json(result["text"])

    debit = await debit_actual_usage(
        db, user,
        model=model, action=action,
        input_tokens=result["input_tokens"], output_tokens=result["output_tokens"],
        key_source=result["key_source"], ref=f"{session_id}:{stage}",
        token_source=result.get("token_source", "estimate"),
        extra_metadata={"pipeline_stage": stage},
    )
    return {
        "parsed": parsed,
        "credits_used": debit.get("credits_charged", 0),
        "balance": debit.get("balance"),
        "duration_ms": duration_ms,
        "model": model,
        "key_source": result["key_source"],
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
    }


class PipelinePaused(Exception):
    def __init__(self, *, stage: str, reason: str, estimate: int = 0, min_credits: int = 1):
        super().__init__(f"Pipeline paused at {stage}: {reason}")
        self.stage = stage
        self.reason = reason
        self.estimate = estimate
        self.min_credits = min_credits


# ─── Persistence helpers ───────────────────────────────
async def _record_stage(db, session_id: str, stage: str, status: str,
                        output: Optional[dict] = None, credits_used: int = 0,
                        duration_ms: int = 0, error: Optional[str] = None):
    """Append/update a stage entry on vibe_sessions.build_progress.
    Idempotent: replaces the entry for the same `stage` if it already exists."""
    entry = {
        "stage": stage, "status": status, "credits_used": credits_used,
        "duration_ms": duration_ms, "timestamp": _now_iso(),
    }
    if output is not None:
        entry["output_summary"] = _summarise(stage, output)
    if error:
        entry["error"] = error[:300]

    # Pull then push (atomic replace by stage)
    await db.vibe_sessions.update_one(
        {"id": session_id},
        {"$pull": {"build_progress": {"stage": stage}}}
    )
    await db.vibe_sessions.update_one(
        {"id": session_id},
        {"$push": {"build_progress": entry},
         "$set": {"build_status": status if status in ("paused", "failed", "running", "complete") else "running",
                  "updated_at": _now_iso()}}
    )


def _summarise(stage: str, output: dict) -> dict:
    """Small summary for UI polling — full output is huge so we trim."""
    if stage == "architect":
        return {"name": output.get("name"), "complexity": output.get("complexity"),
                "has_ui": output.get("has_ui"), "ui_kind": output.get("ui_kind"),
                "integrations": output.get("integrations", [])[:6]}
    if stage == "planner":
        return {"file_count": len(output.get("files", [])),
                "node_count": len(output.get("nodes", [])),
                "dependencies": output.get("dependencies", [])[:8]}
    if stage == "builder":
        return {"file_count": len(output.get("files", [])),
                "total_lines": sum(len((f.get("content") or "").splitlines()) for f in output.get("files", []))}
    if stage == "reviewer":
        return {"fixes_applied": output.get("fixes_applied", []),
                "files_changed": len(output.get("files", []))}
    if stage == "polisher":
        return {"readme_chars": len((output.get("files", [{}])[0].get("content") or ""))}
    if stage == "ui_builder":
        return {"app_chars": len(output.get("app_jsx") or ""),
                "manifest": output.get("manifest", {})}
    return {}


# ─── Resume handling ───────────────────────────────────
async def load_pipeline_state(db, session_id: str) -> dict:
    """Read the persisted pipeline state for resume."""
    sess = await db.vibe_sessions.find_one(
        {"id": session_id},
        {"build_progress": 1, "build_status": 1, "build_context": 1, "_id": 0},
    )
    if not sess:
        return {}
    return {
        "progress": sess.get("build_progress", []),
        "status": sess.get("build_status", "idle"),
        "context": sess.get("build_context", {}),  # parsed outputs by stage
    }


async def _persist_context(db, session_id: str, stage: str, parsed: dict):
    """Cache the parsed output by stage so a resume can skip already-done stages."""
    await db.vibe_sessions.update_one(
        {"id": session_id},
        {"$set": {f"build_context.{stage}": parsed, "updated_at": _now_iso()}},
    )


# ─── Main entry point ──────────────────────────────────
async def run_build_pipeline(
    db,
    user: dict,
    *,
    session_id: str,
    user_prompt: str,
    builder_model: str,
    resume: bool = False,
) -> dict:
    """Execute the 5-stage pipeline (+ optional UI Builder).

    When resume=True, picks up from the last incomplete stage using
    `vibe_sessions.build_context.<stage>` cached outputs.

    Returns:
        {status: 'complete'|'paused'|'failed', project_id, name, files, nodes, edges,
         frontend: {app_jsx, manifest}|None, has_ui, total_credits_used, paused_at?, reason?}
    """
    state = await load_pipeline_state(db, session_id) if resume else {"progress": [], "context": {}}
    context: dict = state.get("context", {})
    done_stages = {p["stage"] for p in state.get("progress", []) if p.get("status") == "done"}

    total_credits = 0
    user_id = str(user.get("id", user.get("email")))

    # Reset failed/paused markers when resuming so retries don't see stale state.
    await db.vibe_sessions.update_one(
        {"id": session_id},
        {"$set": {"build_status": "running", "build_started_at": _now_iso()}}
    )

    try:
        # ── Stage 1: ARCHITECT ──
        if "architect" not in done_stages:
            await _record_stage(db, session_id, "architect", "running")
            arch_user_msg = f"USER REQUEST:\n{user_prompt}\n\nReturn the architecture JSON."
            r = await _run_stage(
                db, user, stage="architect", model=CHEAP_STAGE_MODEL,
                system_prompt=ARCHITECT_PROMPT, user_message=arch_user_msg,
                session_id=session_id,
            )
            architect = r["parsed"]
            context["architect"] = architect
            total_credits += r["credits_used"]
            await _persist_context(db, session_id, "architect", architect)
            await _record_stage(db, session_id, "architect", "done",
                                output=architect, credits_used=r["credits_used"],
                                duration_ms=r["duration_ms"])
        else:
            architect = context.get("architect") or {}

        # ── Stage 2: PLANNER ──
        if "planner" not in done_stages:
            await _record_stage(db, session_id, "planner", "running")
            plan_user_msg = f"ARCHITECT SPEC:\n{json.dumps(architect, indent=2)}\n\nReturn the plan JSON."
            r = await _run_stage(
                db, user, stage="planner", model=CHEAP_STAGE_MODEL,
                system_prompt=PLANNER_PROMPT, user_message=plan_user_msg,
                session_id=session_id,
            )
            planner = r["parsed"]
            context["planner"] = planner
            total_credits += r["credits_used"]
            await _persist_context(db, session_id, "planner", planner)
            await _record_stage(db, session_id, "planner", "done",
                                output=planner, credits_used=r["credits_used"],
                                duration_ms=r["duration_ms"])
        else:
            planner = context.get("planner") or {}

        # ── Stage 3: BUILDER (uses user-selected model) ──
        if "builder" not in done_stages:
            await _record_stage(db, session_id, "builder", "running")
            build_user_msg = (
                f"ARCHITECT SPEC:\n{json.dumps(architect, indent=2)}\n\n"
                f"PLANNER OUTPUT:\n{json.dumps(planner, indent=2)}\n\n"
                "Now write ALL python files. Return the JSON with files."
            )
            r = await _run_stage(
                db, user, stage="builder", model=builder_model,
                system_prompt=BUILDER_PROMPT, user_message=build_user_msg,
                session_id=session_id,
            )
            builder = r["parsed"]
            context["builder"] = builder
            total_credits += r["credits_used"]
            await _persist_context(db, session_id, "builder", builder)
            await _record_stage(db, session_id, "builder", "done",
                                output=builder, credits_used=r["credits_used"],
                                duration_ms=r["duration_ms"])
        else:
            builder = context.get("builder") or {}

        # ── Stage 4: REVIEWER (SKIPPED when AST is clean) ──
        files = builder.get("files") or []
        issues = validate_all_files(files)
        if "reviewer" not in done_stages and issues:
            await _record_stage(db, session_id, "reviewer", "running")
            review_user_msg = (
                f"BUILDER FILE MAP:\n{json.dumps({f['path']: f.get('content', '')[:5000] for f in files}, indent=2)}\n\n"
                f"DETECTED ISSUES:\n{json.dumps(issues, indent=2)}\n\n"
                "Return patched files JSON."
            )
            r = await _run_stage(
                db, user, stage="reviewer", model=CHEAP_STAGE_MODEL,
                system_prompt=REVIEWER_PROMPT, user_message=review_user_msg,
                session_id=session_id,
            )
            reviewer = r["parsed"]
            # Merge reviewer fixes into the builder file map
            patched = reviewer.get("files") or []
            if patched:
                by_path = {f["path"]: f for f in files}
                for p in patched:
                    if p.get("path"):
                        by_path[p["path"]] = p
                files = list(by_path.values())
            context["reviewer"] = reviewer
            total_credits += r["credits_used"]
            await _persist_context(db, session_id, "reviewer", {**reviewer, "files_after": [f["path"] for f in files]})
            await _record_stage(db, session_id, "reviewer", "done",
                                output=reviewer, credits_used=r["credits_used"],
                                duration_ms=r["duration_ms"])
        elif "reviewer" not in done_stages:
            # AST clean → skip reviewer entirely
            await _record_stage(db, session_id, "reviewer", "skipped",
                                output={"fixes_applied": [], "reason": "AST clean — no issues detected"},
                                credits_used=0, duration_ms=0)

        # ── Stage 5: POLISHER ──
        if "polisher" not in done_stages:
            await _record_stage(db, session_id, "polisher", "running")
            polish_user_msg = (
                f"ARCHITECT SPEC:\n{json.dumps(architect, indent=2)}\n\n"
                f"FILE PATHS:\n{json.dumps([f['path'] for f in files], indent=2)}\n\n"
                "Generate README.md. Return JSON."
            )
            r = await _run_stage(
                db, user, stage="polisher", model=CHEAP_STAGE_MODEL,
                system_prompt=POLISHER_PROMPT, user_message=polish_user_msg,
                session_id=session_id,
            )
            polisher = r["parsed"]
            readme_files = polisher.get("files") or []
            if readme_files:
                by_path = {f["path"]: f for f in files}
                for rf in readme_files:
                    if rf.get("path"):
                        by_path[rf["path"]] = rf
                files = list(by_path.values())
            context["polisher"] = polisher
            total_credits += r["credits_used"]
            await _persist_context(db, session_id, "polisher", polisher)
            await _record_stage(db, session_id, "polisher", "done",
                                output=polisher, credits_used=r["credits_used"],
                                duration_ms=r["duration_ms"])

        # ── Stage 6: UI BUILDER (conditional) ──
        has_ui = bool(architect.get("has_ui"))
        frontend = None
        if has_ui and "ui_builder" not in done_stages:
            await _record_stage(db, session_id, "ui_builder", "running")
            ui_user_msg = (
                f"ARCHITECT SPEC:\n{json.dumps(architect, indent=2)}\n\n"
                f"AGENT PURPOSE: {architect.get('purpose', '')}\n\n"
                f"INPUTS: {json.dumps(architect.get('inputs', []), indent=2)}\n"
                f"OUTPUTS: {json.dumps(architect.get('outputs', []), indent=2)}\n\n"
                f"ui_kind={architect.get('ui_kind', 'form')}\n\n"
                "Generate a beautiful single-file React App.jsx. Return JSON."
            )
            r = await _run_stage(
                db, user, stage="ui_builder", model=builder_model,
                system_prompt=UI_BUILDER_PROMPT, user_message=ui_user_msg,
                session_id=session_id,
            )
            ui = r["parsed"]
            frontend = {
                "app_jsx": ui.get("app_jsx", ""),
                "manifest": ui.get("manifest", {}),
            }
            context["ui_builder"] = frontend
            total_credits += r["credits_used"]
            await _persist_context(db, session_id, "ui_builder", frontend)
            await _record_stage(db, session_id, "ui_builder", "done",
                                output=ui, credits_used=r["credits_used"],
                                duration_ms=r["duration_ms"])
        elif has_ui:
            frontend = context.get("ui_builder")

        # ── Finalise: write to bot_projects ──
        nodes = planner.get("nodes") or []
        edges = planner.get("edges") or []
        name = architect.get("name") or "Untitled Agent"
        description = architect.get("description") or ""

        if not files or not nodes:
            raise ValueError("Pipeline produced empty files or nodes — generation failed.")

        now = _now_iso()
        commit_id = uuid.uuid4().hex[:12]
        sess = await db.vibe_sessions.find_one({"id": session_id}, {"project_id": 1, "title": 1, "_id": 0})
        project_id = (sess or {}).get("project_id")
        slug_base = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-") or "agent"
        slug = f"{slug_base}-{uuid.uuid4().hex[:6]}"

        commit_entry = {
            "commit_id": commit_id,
            "message": f"vibe-pipeline: {user_prompt[:120]}",
            "author": user.get("email"),
            "files": files, "nodes": nodes, "edges": edges,
            "model": builder_model, "created_at": now,
        }

        update = {
            "name": name, "description": description,
            "files": files, "nodes": nodes, "edges": edges,
            "has_ui": has_ui, "updated_at": now,
        }
        if frontend:
            update["frontend"] = frontend

        if project_id:
            existing = await db.bot_projects.find_one({"id": project_id, "user_id": user_id}, {"app_slug": 1})
            if not (existing or {}).get("app_slug") and has_ui:
                update["app_slug"] = slug
            await db.bot_projects.update_one(
                {"id": project_id, "user_id": user_id},
                {"$set": update, "$push": {"commit_history": commit_entry}},
            )
        else:
            project_id = uuid.uuid4().hex
            doc = {
                "id": project_id, "user_id": user_id, "creator_email": user.get("email"),
                "language": "python", "prompt": user_prompt[:500],
                "commit_history": [commit_entry], "source": "vibe-pipeline",
                "created_at": now,
                **update,
            }
            if has_ui:
                doc["app_slug"] = slug
            await db.bot_projects.insert_one(doc)

        # Mark session complete
        ai_msg = {
            "role": "assistant",
            "content": f"Generated **{name}** — {len(files)} files, {len(nodes)} nodes" +
                       (f", UI ({architect.get('ui_kind', 'form')})" if has_ui else "") +
                       f". Total: {total_credits} cr.",
            "timestamp": _now_iso(), "type": "build", "credits_used": total_credits,
            "model": builder_model, "project_id": project_id,
        }
        await db.vibe_sessions.update_one(
            {"id": session_id},
            {"$set": {"build_status": "complete", "project_id": project_id,
                      "build_finished_at": _now_iso(), "updated_at": _now_iso()},
             "$inc": {"total_credits_used": total_credits},
             "$push": {"messages": ai_msg}},
        )

        return {
            "status": "complete", "project_id": project_id,
            "name": name, "description": description,
            "files": files, "nodes": nodes, "edges": edges,
            "frontend": frontend, "has_ui": has_ui, "app_slug": slug if has_ui else None,
            "total_credits_used": total_credits,
        }

    except PipelinePaused as p:
        await _record_stage(db, session_id, p.stage, "paused", error=p.reason)
        await db.vibe_sessions.update_one(
            {"id": session_id},
            {"$set": {"build_status": "paused",
                      "build_paused_at": _now_iso(),
                      "build_paused_reason": p.reason,
                      "build_paused_stage": p.stage,
                      "build_paused_estimate": p.estimate,
                      "updated_at": _now_iso()}},
        )
        return {
            "status": "paused", "stage": p.stage, "reason": p.reason,
            "estimate": p.estimate, "min_credits": p.min_credits,
            "total_credits_used": total_credits,
        }
    except Exception as e:
        logger.exception("[pipeline] failed for session=%s", session_id)
        await db.vibe_sessions.update_one(
            {"id": session_id},
            {"$set": {"build_status": "failed",
                      "build_failed_at": _now_iso(),
                      "build_error": str(e)[:300],
                      "updated_at": _now_iso()}},
        )
        return {
            "status": "failed", "error": str(e)[:300],
            "total_credits_used": total_credits,
        }


__all__ = ["run_build_pipeline", "validate_all_files", "load_pipeline_state", "PipelinePaused"]
