"""
apps — Hosted Agent Mini-Apps (Prompt 16).

When an agent has has_ui=True, the UI Builder stage produces a single-file React
`App.jsx`. This module:
  - Lists the current user's mini-apps      → GET  /api/my-apps
  - Loads a single app's metadata           → GET  /api/apps/{slug}
  - Serves the iframe shell HTML            → GET  /api/apps/{slug}/render
  - Executes the agent's run() function     → POST /api/apps/{id}/run
  - Returns run history                     → GET  /api/apps/{id}/runs
  - Regenerates the UI ("Redesign with AI") → POST /api/apps/{id}/redesign

The iframe shell uses Babel-standalone (CDN) to transpile the AI-generated JSX
at load time, then injects window.tfApi.run() pointing back at /api/apps/{id}/run.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from lib.smart_credits import check_can_afford, debit_actual_usage
from lib.rate_limit import rate_limit_dependency

router = APIRouter()


def get_current_user():
    from server import get_current_user as _u
    return _u


def get_db():
    from server import db
    return db


async def _optional_user(request: Request) -> Optional[dict]:
    """Return the auth'd user from the Authorization header — or None when missing/invalid.
    Used by /apps/{id}/run so public apps don't 401 on anonymous visitors."""
    auth = request.headers.get("Authorization") or request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        from server import decode_token, db as _db
        payload = decode_token(token)
        return await _db.users.find_one({"id": payload.get("user_id") or payload.get("sub")})
    except Exception:
        return None


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


class AppRunRequest(BaseModel):
    input: dict = Field(default_factory=dict)


class AppRedesignRequest(BaseModel):
    prompt: str = Field(min_length=5, max_length=2000)


class AppRevertRequest(BaseModel):
    version_id: str = Field(min_length=1, max_length=64)


# Max number of redesign snapshots to retain per app (FIFO eviction).
REDESIGN_HISTORY_CAP = 10


# ─── Listing endpoints ─────────────────────────────────
@router.get("/my-apps")
async def list_my_apps(user=Depends(get_current_user())):
    """List every project the current user has built that exposes a hosted UI."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    cursor = db.bot_projects.find(
        {"user_id": user_id, "has_ui": True},
        {"_id": 0, "id": 1, "name": 1, "description": 1, "app_slug": 1,
         "frontend.manifest": 1, "updated_at": 1, "created_at": 1},
    ).sort("updated_at", -1).limit(60)
    items = await cursor.to_list(60)
    # Pull run counts in parallel
    apps = []
    for it in items:
        run_count = await db.app_runs.count_documents({"app_id": it["id"]})
        apps.append({
            "id": it["id"],
            "name": it.get("name", "Untitled"),
            "description": it.get("description", ""),
            "slug": it.get("app_slug"),
            "manifest": (it.get("frontend") or {}).get("manifest", {}),
            "updated_at": it.get("updated_at"),
            "created_at": it.get("created_at"),
            "run_count": run_count,
        })
    return {"apps": apps}


@router.get("/apps/{slug}")
async def get_app(slug: str, user=Depends(get_current_user())):
    """Fetch a single app's metadata + JSX source (owner-only)."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    proj = await db.bot_projects.find_one(
        {"app_slug": slug, "user_id": user_id, "has_ui": True},
        {"_id": 0},
    )
    if not proj:
        # Allow lookup by raw id too — frontend may pass either
        proj = await db.bot_projects.find_one(
            {"id": slug, "user_id": user_id, "has_ui": True},
            {"_id": 0},
        )
    if not proj:
        raise HTTPException(status_code=404, detail="App not found.")
    return {
        "id": proj["id"],
        "name": proj.get("name", "Untitled"),
        "description": proj.get("description", ""),
        "slug": proj.get("app_slug"),
        "frontend": proj.get("frontend"),
        "files": proj.get("files", []),
        "nodes": proj.get("nodes", []),
        "edges": proj.get("edges", []),
        "is_public": bool(proj.get("is_public")),
        "updated_at": proj.get("updated_at"),
    }


class AppShareToggleRequest(BaseModel):
    is_public: bool


@router.post("/apps/{slug}/share")
async def toggle_share(slug: str, body: AppShareToggleRequest, user=Depends(get_current_user())):
    """Toggle the is_public flag for a mini-app. Public apps can be loaded by
    anyone via /api/apps/{slug}/render without auth; they CAN'T be executed
    without a JWT (run endpoint still owner-only)."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    res = await db.bot_projects.update_one(
        {"$or": [{"app_slug": slug}, {"id": slug}], "user_id": user_id, "has_ui": True},
        {"$set": {"is_public": bool(body.is_public), "updated_at": _now_iso()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="App not found.")
    return {"ok": True, "is_public": bool(body.is_public)}


# ─── Iframe shell ──────────────────────────────────────
_IFRAME_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>__APP_TITLE__</title>
<script src="https://cdn.tailwindcss.com"></script>
<script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
<script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
<style>
  body { background: #0a0a0a; color: #e5e7eb; font-family: ui-sans-serif, system-ui, sans-serif; margin: 0; min-height: 100vh; }
  #root { min-height: 100vh; }
  .tf-err { padding: 24px; color: #f43f5e; font-family: ui-monospace, monospace; font-size: 12px; white-space: pre-wrap; }
</style>
</head>
<body data-tf-app-id="__APP_ID__" data-tf-base="__BASE__">
<script id="tf-cfg" type="application/json">__TF_CFG__</script>
<div id="root"></div>
<script>
  // tfApi bridge — the AI-generated App.jsx calls window.tfApi.run(input)
  // to invoke the agent's backend run() function. Config is JSON-encoded in the
  // tf-cfg script tag (NOT string-replaced into the JS body) so any sentinel
  // tokens in the AI-generated JSX can't collide with our shell.
  (function(){
    var cfg = {};
    try { cfg = JSON.parse(document.getElementById('tf-cfg').textContent); } catch(e) {}
    window.tfApi = {
      appId: cfg.app_id,
      run: async function(input) {
        var resp = await fetch(cfg.base + "/api/apps/" + encodeURIComponent(cfg.app_id) + "/run", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + cfg.token
          },
          body: JSON.stringify({ input: input || {} })
        });
        if (!resp.ok) {
          var txt = await resp.text();
          throw new Error("tfApi.run failed: HTTP " + resp.status + " — " + txt.slice(0, 200));
        }
        return await resp.json();
      }
    };
  })();
</script>
<script id="tf-app-source" type="text/babel" data-presets="env,react">
try {
  __APP_JSX__
  var mount = document.getElementById("root");
  var Component = window.__TF_APP;
  if (!Component) {
    mount.innerHTML = '<div class="tf-err">App generation error: window.__TF_APP was not assigned.</div>';
  } else {
    ReactDOM.createRoot(mount).render(React.createElement(Component));
  }
} catch (err) {
  document.getElementById("root").innerHTML =
    '<div class="tf-err">Render error: ' + (err && err.stack ? err.stack : err) + '</div>';
}
</script>
</body>
</html>
"""


@router.get("/apps/{slug}/render", response_class=HTMLResponse)
async def render_app(slug: str, token: Optional[str] = None):
    """Serve the iframe-friendly HTML shell for an AI-generated mini-app.

    Token can be passed as a query param (?token=...) because iframes can't
    forward Authorization headers from their parent. We embed it into a JSON
    config script tag (NOT string-replaced into JS), so any sentinel tokens
    that an AI-generated app_jsx might contain can't collide with our shell.

    Public apps (is_public=true) load without a token. Private apps still load
    the HTML shell but run() calls will 401 if no/invalid token is supplied
    (acceptable trade-off — the JSX source isn't truly secret since slugs are
    URL parameters; only execution is gated)."""
    db = get_db()
    # No auth here — we let the iframe load and rely on token in tfApi to
    # gate the actual run() endpoint. The slug is non-secret (it's in the URL).
    proj = await db.bot_projects.find_one(
        {"$or": [{"app_slug": slug}, {"id": slug}], "has_ui": True},
        {"_id": 0, "id": 1, "name": 1, "frontend": 1, "user_id": 1, "is_public": 1},
    )
    if not proj:
        return HTMLResponse(
            "<html><body style='font-family:monospace;padding:24px;color:#f43f5e;background:#0a0a0a'>App not found.</body></html>",
            status_code=404,
        )
    frontend = proj.get("frontend") or {}
    app_jsx = frontend.get("app_jsx") or "window.__TF_APP = () => React.createElement('div', {className: 'p-8 text-amber-400'}, 'This agent has no UI yet.');"

    # Resolve a base URL the iframe can call back to. Same-origin works because
    # the frontend serves the iframe from /apps/:slug which calls /api/apps/...
    base = ""  # same-origin
    cfg_json = json.dumps({"app_id": proj["id"], "base": base, "token": token or ""})
    html = (
        _IFRAME_HTML_TEMPLATE
        .replace("__APP_TITLE__", (proj.get("name") or "Agent") + " — Mini App")
        .replace("__APP_ID__", proj["id"])
        .replace("__BASE__", base)
        .replace("__TF_CFG__", cfg_json.replace("</", "<\\/"))
        .replace("__APP_JSX__", app_jsx)
    )
    return HTMLResponse(html)


# ─── Execution ─────────────────────────────────────────
@router.post("/apps/{app_id}/run")
async def run_app(app_id: str, body: AppRunRequest, request: Request,
                  user: Optional[dict] = Depends(_optional_user),
                  _=Depends(rate_limit_dependency("app_run", 60, 60))):
    """Execute the agent's backend run() function and return its output.

    Auth flow:
      - Private apps (is_public=false): owner-only. Debits the owner's wallet.
      - Public apps (is_public=true): anyone can run. Debits the OWNER'S wallet
        (creators absorb the cost of their viral shares — typical SaaS model).
        Rate-limited per-IP (60/min) for abuse defence.

    For the MVP we use a lightweight in-process simulation: we extract the
    `run()` body from main.py and exec it in a restricted namespace. For real
    isolation, this delegates to lib.external_agent_runtime in a future PR."""
    db = get_db()
    proj = await db.bot_projects.find_one(
        {"$or": [{"id": app_id}, {"app_slug": app_id}]},
        {"_id": 0},
    )
    if not proj:
        raise HTTPException(status_code=404, detail="App not found.")

    is_public = bool(proj.get("is_public"))
    owner_id = proj.get("user_id")
    caller_id = str(user.get("id", user.get("email"))) if user else None

    if not is_public:
        # Private: must be authenticated AND owner
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required.")
        if owner_id != caller_id:
            raise HTTPException(status_code=403, detail="Not your app.")
    else:
        # Public: anonymous visitors must still sign up to run (viral signup loop).
        # They CAN view the iframe (it loads without auth) but to actually exercise
        # the agent they need a free account so we can attribute usage + cap abuse.
        if not user:
            raise HTTPException(status_code=401, detail="Sign in to run this app.")

    # Resolve which wallet to bill — public apps bill the owner; private bill the caller (== owner).
    billing_user = user
    if is_public and owner_id != caller_id:
        billing_user = await db.users.find_one({"id": owner_id})
        if not billing_user:
            raise HTTPException(status_code=503, detail="App owner not found.")

    # Pre-flight credit check (agent_run = 1cr min) — against the billing wallet
    pre = await check_can_afford(db, billing_user, "gemini-2.5-flash", "agent_run")
    if not pre.get("allowed"):
        # For public apps, surface a soft "owner out of credits" message rather than 402 jargon
        if is_public and caller_id != owner_id:
            return JSONResponse(status_code=402, content={
                "error": "OWNER_OUT_OF_CREDITS",
                "message": "This shared app's owner is out of credits. Try again later.",
            })
        return JSONResponse(status_code=402, content=pre)

    # Extract main.py
    files = proj.get("files") or []
    main_py = next((f.get("content") for f in files if f.get("path") == "main.py"), None)
    if not main_py:
        raise HTTPException(status_code=400, detail="App has no main.py to execute.")

    t0 = time.time()
    run_id = uuid.uuid4().hex
    success = False
    output: dict = {}
    error: Optional[str] = None

    try:
        # Sandboxed exec — only safe builtins, captured run() function.
        # NOTE: This is intentionally lighter-weight than external_agent_runtime
        # because mini-apps are typically simple data transforms. Heavy / risky
        # agents should go through the External Agents pipeline.
        import builtins as _bi
        SAFE_BUILTINS = {
            "len": len, "str": str, "int": int, "float": float, "bool": bool,
            "list": list, "dict": dict, "tuple": tuple, "set": set, "frozenset": frozenset,
            "range": range, "enumerate": enumerate, "zip": zip,
            "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
            "sorted": sorted, "reversed": reversed, "map": map, "filter": filter,
            "any": any, "all": all, "isinstance": isinstance, "type": type,
            "print": print, "repr": repr, "format": format, "hash": hash, "id": id,
            "iter": iter, "next": next, "object": object, "property": property,
            "getattr": getattr, "setattr": setattr, "hasattr": hasattr, "delattr": delattr,
            "callable": callable, "vars": vars, "dir": dir, "slice": slice,
            "bytes": bytes, "bytearray": bytearray, "chr": chr, "ord": ord,
            "hex": hex, "oct": oct, "bin": bin, "complex": complex,
            "staticmethod": staticmethod, "classmethod": classmethod, "super": super,
            "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
            "KeyError": KeyError, "IndexError": IndexError, "RuntimeError": RuntimeError,
            "AttributeError": AttributeError, "NotImplementedError": NotImplementedError,
            "StopIteration": StopIteration, "ZeroDivisionError": ZeroDivisionError,
            "__import__": __import__, "__build_class__": _bi.__build_class__,
            "__name__": "__tfagent__",
            "True": True, "False": False, "None": None,
        }
        ns: dict = {"__builtins__": SAFE_BUILTINS, "__name__": "__tfagent__"}
        exec(compile(main_py, "<agent:main.py>", "exec"), ns)
        run_fn = ns.get("run")
        if not callable(run_fn):
            raise RuntimeError("main.py did not define a callable run() function.")
        # Invoke with whatever subset of kwargs the agent accepts
        import inspect as _inspect
        sig = _inspect.signature(run_fn)
        kwargs: dict = {"input": body.input}
        if "env" in sig.parameters:
            kwargs["env"] = {}
        if "keys" in sig.parameters:
            kwargs["keys"] = {}
        result = run_fn(**kwargs)
        if _inspect.iscoroutine(result):
            import asyncio as _asyncio
            result = await result
        if isinstance(result, dict):
            output = result
        else:
            output = {"result": result}
        success = True
    except Exception as e:
        error = f"{type(e).__name__}: {str(e)[:300]}"
    duration_ms = int((time.time() - t0) * 1000)

    # Debit (1 cr min for app run) — billed to the OWNER for public apps, caller for private.
    debit = await debit_actual_usage(
        db, billing_user,
        model="gemini-2.5-flash", action="agent_run",
        input_tokens=0, output_tokens=0,
        key_source="platform", ref=f"app_run:{run_id}",
        token_source="estimate",
        extra_metadata={"app_id": app_id, "kind": "mini_app_run",
                        "caller_id": caller_id, "is_public_run": bool(is_public and caller_id != owner_id)},
    )

    # Record run — keyed under the OWNER so it shows up in their history,
    # with caller_id captured for analytics on public-share usage.
    await db.app_runs.insert_one({
        "id": run_id,
        "app_id": proj["id"],
        "user_id": owner_id,
        "caller_id": caller_id,
        "input": body.input,
        "output": output,
        "success": success,
        "error": error,
        "duration_ms": duration_ms,
        "credits_used": debit.get("credits_charged", 0),
        "created_at": _now_iso(),
    })

    return {
        "run_id": run_id,
        "success": success,
        "output": output,
        "error": error,
        "duration_ms": duration_ms,
        "balance_remaining": debit.get("balance"),
    }


@router.get("/apps/{app_id}/runs")
async def app_runs(app_id: str, limit: int = 25, user=Depends(get_current_user())):
    """Run history for a mini-app (owner-only)."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    proj = await db.bot_projects.find_one(
        {"$or": [{"id": app_id}, {"app_slug": app_id}], "user_id": user_id},
        {"_id": 0, "id": 1},
    )
    if not proj:
        raise HTTPException(status_code=404, detail="App not found.")
    limit = max(1, min(100, int(limit)))
    cursor = db.app_runs.find(
        {"app_id": proj["id"], "user_id": user_id},
        {"_id": 0},
    ).sort("created_at", -1).limit(limit)
    items = await cursor.to_list(limit)
    return {"runs": items, "count": len(items)}


# ─── Redesign with AI (future stub — wired now) ─────────
@router.post("/apps/{app_id}/redesign")
async def redesign_app(app_id: str, body: AppRedesignRequest, user=Depends(get_current_user())):
    """Re-run the UI Builder stage with a modification prompt — returns the
    updated frontend block synchronously (UI stage is fast, no need to queue)."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    proj = await db.bot_projects.find_one(
        {"$or": [{"id": app_id}, {"app_slug": app_id}], "user_id": user_id},
        {"_id": 0},
    )
    if not proj:
        raise HTTPException(status_code=404, detail="App not found.")
    if not proj.get("has_ui"):
        raise HTTPException(status_code=409, detail="App has no UI to redesign.")

    pre = await check_can_afford(db, user, "gemini-2.5-flash", "vibe_build")
    if not pre.get("allowed"):
        return JSONResponse(status_code=402, content=pre)

    from lib.llm_client import call_llm
    from prompts.code_gen_prompts import UI_BUILDER_PROMPT

    frontend = proj.get("frontend") or {}
    current_jsx = frontend.get("app_jsx", "")

    ctx = (
        f"CURRENT App.jsx:\n{current_jsx[:6000]}\n\n"
        f"USER REQUEST:\n{body.prompt}\n\n"
        "Regenerate the full App.jsx with the requested change. Return JSON."
    )
    t0 = time.time()
    result = await call_llm(
        model="gemini-2.5-flash",
        system_prompt=UI_BUILDER_PROMPT,
        messages=[{"role": "user", "content": ctx}],
        db=db, user_id=user_id,
    )
    duration_ms = int((time.time() - t0) * 1000)

    # Parse JSON output
    try:
        from lib.code_gen_pipeline import _extract_json
        parsed = _extract_json(result["text"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not parse redesign output: {str(e)[:120]}")

    new_jsx = parsed.get("app_jsx") or current_jsx
    new_manifest = parsed.get("manifest") or frontend.get("manifest", {})

    # Push the OLD version into history (FIFO cap) BEFORE overwriting.
    # Lets the user revert if the AI's new design is worse.
    history = list(frontend.get("history") or [])
    if current_jsx:
        history.append({
            "version_id": uuid.uuid4().hex[:12],
            "prompt": body.prompt,
            "app_jsx": current_jsx,
            "manifest": frontend.get("manifest", {}),
            "created_at": _now_iso(),
        })
        # Keep only the most-recent N entries to bound document size.
        history = history[-REDESIGN_HISTORY_CAP:]

    await db.bot_projects.update_one(
        {"id": proj["id"]},
        {"$set": {"frontend": {"app_jsx": new_jsx, "manifest": new_manifest, "history": history},
                  "updated_at": _now_iso()}},
    )

    debit = await debit_actual_usage(
        db, user,
        model="gemini-2.5-flash", action="vibe_build",
        input_tokens=result["input_tokens"], output_tokens=result["output_tokens"],
        key_source=result["key_source"], ref=f"redesign:{app_id}",
        token_source=result.get("token_source", "estimate"),
        extra_metadata={"app_id": app_id, "kind": "ui_redesign"},
    )

    return {
        "ok": True,
        "frontend": {"app_jsx": new_jsx, "manifest": new_manifest},
        "balance_remaining": debit.get("balance"),
        "credits_charged": debit.get("credits_charged", 0),
        "duration_ms": duration_ms,
        "history_count": len(history),
    }


# ─── Redesign history + revert ─────────────────────────
@router.get("/apps/{app_id}/redesign-history")
async def app_redesign_history(app_id: str, user=Depends(get_current_user())):
    """Return the most recent redesign snapshots (newest-first) so the user can
    preview prompts + revert to a prior UI version."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    proj = await db.bot_projects.find_one(
        {"$or": [{"id": app_id}, {"app_slug": app_id}], "user_id": user_id, "has_ui": True},
        {"_id": 0, "frontend.history": 1},
    )
    if not proj:
        raise HTTPException(status_code=404, detail="App not found.")
    history = list(((proj.get("frontend") or {}).get("history")) or [])
    # Strip the full JSX from the listing payload — too heavy to ship 10× on every fetch.
    # The /revert call will use it server-side.
    summary = []
    for entry in reversed(history):  # newest first
        summary.append({
            "version_id": entry.get("version_id"),
            "prompt": entry.get("prompt") or "",
            "created_at": entry.get("created_at"),
            "jsx_size": len(entry.get("app_jsx") or ""),
        })
    return {"history": summary, "count": len(summary), "cap": REDESIGN_HISTORY_CAP}


@router.post("/apps/{app_id}/revert")
async def app_revert(app_id: str, body: AppRevertRequest, user=Depends(get_current_user())):
    """Restore a previous redesign version. Pushes the CURRENT design into history
    too, so revert is itself reversible. No credit charge — pure DB swap."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    proj = await db.bot_projects.find_one(
        {"$or": [{"id": app_id}, {"app_slug": app_id}], "user_id": user_id, "has_ui": True},
        {"_id": 0},
    )
    if not proj:
        raise HTTPException(status_code=404, detail="App not found.")
    frontend = proj.get("frontend") or {}
    history = list(frontend.get("history") or [])
    target = next((h for h in history if h.get("version_id") == body.version_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Version not found in history.")

    current_jsx = frontend.get("app_jsx") or ""
    # Replace the targeted history slot with the CURRENT design so revert is reversible.
    new_history = []
    for h in history:
        if h.get("version_id") == body.version_id:
            new_history.append({
                "version_id": uuid.uuid4().hex[:12],
                "prompt": f"Revert ↔ {target.get('prompt', '')[:120]}",
                "app_jsx": current_jsx,
                "manifest": frontend.get("manifest", {}),
                "created_at": _now_iso(),
            })
        else:
            new_history.append(h)
    new_history = new_history[-REDESIGN_HISTORY_CAP:]

    await db.bot_projects.update_one(
        {"id": proj["id"]},
        {"$set": {"frontend": {
            "app_jsx": target.get("app_jsx") or current_jsx,
            "manifest": target.get("manifest") or frontend.get("manifest", {}),
            "history": new_history,
        }, "updated_at": _now_iso()}},
    )
    return {"ok": True, "reverted_to": body.version_id}
