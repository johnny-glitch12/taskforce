"""
n8n White-Label Proxy — Reverse proxies n8n's editor and API,
rewriting all branding to "The Armory by Task Force AI".
Also manages per-user workflow isolation and compute credit gating.
"""
import os
import re
import httpx
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

N8N_BASE_URL = os.environ.get("N8N_BASE_URL", "")
N8N_API_KEY = os.environ.get("N8N_API_KEY", "")

# ── Theme CSS injected into every n8n HTML page ──
THEME_CSS = """
<style id="taskforce-theme">
  /* ═══ HIDE ALL N8N BRANDING ═══ */
  [class*="n8n-logo"], [data-test-id*="n8n-logo"],
  .n8n-logo, .el-dialog__title:has-text("n8n"),
  [class*="aboutModal"], .about-modal,
  footer[class*="n8n"], [class*="bannerStack"],
  [data-test-id="banner-stack"], [class*="askAi"] { display: none !important; }

  /* ═══ COLOR OVERHAUL: n8n orange/purple → Task Force cyan/black ═══ */
  :root {
    --color-primary: #22d3ee !important;
    --color-primary-shade-1: #06b6d4 !important;
    --color-primary-tint-1: #67e8f9 !important;
    --color-primary-tint-2: #a5f3fc !important;
    --color-primary-tint-3: #cffafe !important;
    --color-secondary: #10b981 !important;
    --color-background-dark: #000000 !important;
    --color-background-base: #09090b !important;
    --color-background-light: #0a0a0c !important;
    --color-background-lighter: #111113 !important;
    --color-background-xlight: #18181b !important;
    --color-foreground-dark: #e4e4e7 !important;
    --color-foreground-base: #a1a1aa !important;
    --color-foreground-light: #71717a !important;
    --color-foreground-xlight: #3f3f46 !important;
    --color-text-dark: #e4e4e7 !important;
    --color-text-base: #a1a1aa !important;
    --color-text-light: #71717a !important;
    --color-text-xlight: #52525b !important;
    --border-color-base: #27272a !important;
    --border-color-light: #1a1a1e !important;
    --color-canvas-background: #000000 !important;
    --color-canvas-dot: rgba(34, 211, 238, 0.08) !important;
    --color-node-background: #111113 !important;
    --color-sticky-background: #18181b !important;
    --color-success: #10b981 !important;
    --color-danger: #ef4444 !important;
    --color-warning: #f59e0b !important;
  }

  /* Force dark backgrounds */
  body, #app, .el-main, .workflow-canvas {
    background-color: #000000 !important;
    color: #e4e4e7 !important;
  }

  /* Font override */
  body, .el-input__inner, .el-textarea__inner, .el-button, .el-select,
  .el-dialog__title, code, pre {
    font-family: 'Inter', 'JetBrains Mono', monospace !important;
  }

  /* Sidebar dark theme */
  .el-menu, .sidebar-content, [class*="sidebar"], nav {
    background-color: #09090b !important;
    border-color: #1a1a1e !important;
  }

  /* Node styling */
  .node-default { border-radius: 4px !important; border-color: #27272a !important; }
  .node-default:hover { border-color: #22d3ee !important; }
  .node-default.selected { border-color: #22d3ee !important; box-shadow: 0 0 20px rgba(34,211,238,0.15) !important; }

  /* Buttons */
  .el-button--primary { background-color: #22d3ee !important; border-color: #22d3ee !important; color: #000 !important; border-radius: 2px !important; }
  .el-button--primary:hover { background-color: #06b6d4 !important; }

  /* Inputs */
  .el-input__inner, .el-textarea__inner {
    background-color: rgba(255,255,255,0.03) !important;
    border-color: #27272a !important;
    color: #e4e4e7 !important;
    border-radius: 2px !important;
  }
  .el-input__inner:focus, .el-textarea__inner:focus { border-color: #22d3ee !important; }

  /* Dialogs/Modals */
  .el-dialog, .el-drawer { background-color: #0a0a0c !important; border-color: #1a1a1e !important; border-radius: 2px !important; }
  .el-dialog__header { border-bottom: 1px solid #1a1a1e !important; }

  /* Scrollbar */
  ::-webkit-scrollbar { width: 4px; height: 4px; }
  ::-webkit-scrollbar-track { background: #000; }
  ::-webkit-scrollbar-thumb { background: #27272a; }
</style>
"""

# ── Text replacements for white-labeling ──
BRAND_REPLACEMENTS = [
    ("n8n", "The Armory"),
    ("N8N", "THE ARMORY"),
    ("<title>n8n", "<title>The Armory"),
    ("<title>Editor", "<title>The Armory"),
    ("n8n.io", "taskforceai.com"),
    ("Automate without limits", "Build autonomous workflows"),
    ("n8n GmbH", "Task Force AI"),
    ("n8n workflow automation", "The Armory workflow builder"),
]


def get_current_user():
    from server import get_current_user as _get_user
    return _get_user


def get_db():
    from server import db
    return db


def _rewrite_html(content: str) -> str:
    """Rewrite HTML content to strip n8n branding and inject our theme."""
    for old, new in BRAND_REPLACEMENTS:
        content = content.replace(old, new)

    # Inject theme CSS before </head>
    if "</head>" in content:
        content = content.replace("</head>", THEME_CSS + "</head>")

    return content


def _get_n8n_headers():
    """Headers for authenticating with n8n's API."""
    headers = {}
    if N8N_API_KEY:
        headers["X-N8N-API-KEY"] = N8N_API_KEY
    return headers


def _is_configured():
    return bool(N8N_BASE_URL)


# ──────────────────────────────────────────────
# Health / Status Check
# ──────────────────────────────────────────────
@router.get("/n8n/status")
async def n8n_status(user=Depends(get_current_user())):
    """Check if n8n engine is configured and reachable."""
    if not _is_configured():
        return {"connected": False, "message": "Execution engine not configured. Set N8N_BASE_URL in backend .env"}

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            res = await client.get(f"{N8N_BASE_URL}/healthz", headers=_get_n8n_headers())
            return {"connected": res.status_code == 200, "url": N8N_BASE_URL}
    except Exception as e:
        return {"connected": False, "message": f"Cannot reach engine: {str(e)}"}


# ──────────────────────────────────────────────
# Workflow CRUD (wraps n8n API with user isolation)
# ──────────────────────────────────────────────
@router.get("/n8n/workflows")
async def list_workflows(user=Depends(get_current_user())):
    """List workflows owned by the current user."""
    if not _is_configured():
        raise HTTPException(status_code=503, detail="Execution engine not configured.")

    db = get_db()
    user_id = str(user.get("id", user.get("email")))

    # Get user's n8n workflow IDs from our mapping table
    mappings = await db.n8n_workflow_map.find({"user_id": user_id}, {"_id": 0}).to_list(500)
    n8n_ids = [m["n8n_workflow_id"] for m in mappings]

    if not n8n_ids:
        return {"workflows": []}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(f"{N8N_BASE_URL}/api/v1/workflows", headers=_get_n8n_headers())
            if res.status_code != 200:
                return {"workflows": []}
            all_wf = res.json().get("data", [])
            # Filter to only user's workflows
            user_wf = [wf for wf in all_wf if str(wf.get("id")) in n8n_ids]
            return {"workflows": user_wf}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Engine error: {str(e)}")


@router.post("/n8n/workflows/import")
async def import_template(request: Request, user=Depends(get_current_user())):
    """Import a template into the user's workspace (creates a copy in n8n)."""
    if not _is_configured():
        raise HTTPException(status_code=503, detail="Execution engine not configured.")

    body = await request.json()
    template_id = body.get("template_id")
    workflow_json = body.get("workflow")

    if not workflow_json:
        raise HTTPException(status_code=400, detail="No workflow JSON provided.")

    db = get_db()
    user_id = str(user.get("id", user.get("email")))

    # Create workflow in n8n
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(
                f"{N8N_BASE_URL}/api/v1/workflows",
                headers={**_get_n8n_headers(), "Content-Type": "application/json"},
                json=workflow_json,
            )
            if res.status_code not in (200, 201):
                raise HTTPException(status_code=502, detail=f"Engine rejected workflow: {res.text[:200]}")

            n8n_wf = res.json()
            n8n_id = str(n8n_wf.get("id"))

            # Map to user
            now = datetime.now(timezone.utc).isoformat()
            await db.n8n_workflow_map.insert_one({
                "user_id": user_id,
                "n8n_workflow_id": n8n_id,
                "template_id": template_id,
                "name": workflow_json.get("name", "Imported Workflow"),
                "created_at": now,
            })

            return {"success": True, "workflow_id": n8n_id, "name": n8n_wf.get("name")}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Engine error: {str(e)}")


@router.post("/n8n/workflows/{workflow_id}/execute")
async def execute_workflow(workflow_id: str, request: Request, user=Depends(get_current_user())):
    """Execute a workflow — gated by compute credits."""
    if not _is_configured():
        raise HTTPException(status_code=503, detail="Execution engine not configured.")

    db = get_db()
    user_id = str(user.get("id", user.get("email")))

    # Verify ownership
    mapping = await db.n8n_workflow_map.find_one({"user_id": user_id, "n8n_workflow_id": workflow_id})
    if not mapping:
        raise HTTPException(status_code=403, detail="You don't own this workflow.")

    # Compute credit check
    from lib.compute_credits import check_compute_credits, increment_compute_usage
    credit_check = await check_compute_credits(db, user)
    if credit_check.get("allowed") is False:
        return credit_check

    # Execute via n8n API
    body = await request.json() if await request.body() else {}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.post(
                f"{N8N_BASE_URL}/api/v1/workflows/{workflow_id}/run",
                headers={**_get_n8n_headers(), "Content-Type": "application/json"},
                json=body,
            )
            result = res.json()

            # Increment compute usage on successful dispatch
            await increment_compute_usage(db, user)

            # Log execution
            now = datetime.now(timezone.utc).isoformat()
            await db.n8n_executions.insert_one({
                "user_id": user_id,
                "workflow_id": workflow_id,
                "status": "completed" if res.status_code == 200 else "failed",
                "result_preview": str(result)[:500],
                "created_at": now,
            })

            return {"success": res.status_code == 200, "data": result}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Execution error: {str(e)}")


@router.delete("/n8n/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str, user=Depends(get_current_user())):
    """Delete a user's workflow from both n8n and our mapping."""
    if not _is_configured():
        raise HTTPException(status_code=503, detail="Execution engine not configured.")

    db = get_db()
    user_id = str(user.get("id", user.get("email")))

    mapping = await db.n8n_workflow_map.find_one({"user_id": user_id, "n8n_workflow_id": workflow_id})
    if not mapping:
        raise HTTPException(status_code=404, detail="Workflow not found.")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.delete(f"{N8N_BASE_URL}/api/v1/workflows/{workflow_id}", headers=_get_n8n_headers())
    except Exception:
        pass  # Delete from our side even if n8n is unreachable

    await db.n8n_workflow_map.delete_one({"_id": mapping["_id"]})
    return {"success": True}


# ──────────────────────────────────────────────
# BYOK Credential Vault
# ──────────────────────────────────────────────
@router.post("/n8n/credentials")
async def save_credentials(request: Request, user=Depends(get_current_user())):
    """Store user's API credentials (BYOK) for workflow execution."""
    body = await request.json()
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    now = datetime.now(timezone.utc).isoformat()

    cred_name = body.get("name", "")
    cred_type = body.get("type", "")
    cred_data = body.get("data", {})

    if not cred_name or not cred_type:
        raise HTTPException(status_code=400, detail="Name and type required.")

    await db.n8n_credentials.update_one(
        {"user_id": user_id, "name": cred_name},
        {"$set": {
            "type": cred_type,
            "data": cred_data,  # In production: encrypt this
            "updated_at": now,
        }, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return {"success": True, "message": f"Credential '{cred_name}' saved."}


@router.get("/n8n/credentials")
async def list_credentials(user=Depends(get_current_user())):
    """List user's stored credentials (keys masked)."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    creds = await db.n8n_credentials.find({"user_id": user_id}, {"_id": 0}).to_list(100)
    # Mask sensitive data
    for c in creds:
        if "data" in c:
            c["data"] = {k: "••••" + str(v)[-4:] if len(str(v)) > 4 else "••••" for k, v in c["data"].items()}
    return {"credentials": creds}


@router.delete("/n8n/credentials/{cred_name}")
async def delete_credential(cred_name: str, user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    result = await db.n8n_credentials.delete_one({"user_id": user_id, "name": cred_name})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Credential not found.")
    return {"success": True}


# ──────────────────────────────────────────────
# Editor Proxy — Serves n8n UI with rebranding
# ──────────────────────────────────────────────
@router.get("/n8n/editor/{path:path}")
async def proxy_editor(path: str, request: Request, user=Depends(get_current_user())):
    """Reverse proxy n8n's web editor with full branding replacement."""
    if not _is_configured():
        return HTMLResponse("<h1>Execution engine not configured</h1>", status_code=503)

    target_url = f"{N8N_BASE_URL}/{path}"
    if request.query_params:
        target_url += f"?{request.query_params}"

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            res = await client.get(target_url, headers=_get_n8n_headers())

            content_type = res.headers.get("content-type", "")

            # Rewrite HTML content
            if "text/html" in content_type:
                html = res.text
                rewritten = _rewrite_html(html)
                return HTMLResponse(content=rewritten, status_code=res.status_code)

            # Rewrite CSS/JS for branding strings
            if "javascript" in content_type or "css" in content_type:
                text = res.text
                for old, new in BRAND_REPLACEMENTS:
                    text = text.replace(old, new)
                return Response(content=text, status_code=res.status_code, media_type=content_type)

            # Pass through binary/other content
            return Response(
                content=res.content,
                status_code=res.status_code,
                media_type=content_type,
            )
    except Exception as e:
        return HTMLResponse(f"<h1>Engine unreachable</h1><p>{str(e)}</p>", status_code=502)


# ──────────────────────────────────────────────
# Setup Guide endpoint
# ──────────────────────────────────────────────
@router.get("/n8n/setup-guide")
async def get_setup_guide(user=Depends(get_current_user())):
    """Return n8n self-hosting setup instructions."""
    return {
        "title": "Connect Your Execution Engine",
        "steps": [
            {
                "step": 1,
                "title": "Deploy n8n on your VPS",
                "command": "docker run -d --name n8n -p 5678:5678 -e N8N_BASIC_AUTH_ACTIVE=false -e WEBHOOK_URL=https://your-vps.com/ -v n8n_data:/home/node/.n8n n8nio/n8n",
                "note": "Replace 'your-vps.com' with your actual domain. Minimum: 2GB RAM VPS ($5-10/mo)."
            },
            {
                "step": 2,
                "title": "Generate an API key",
                "command": "In n8n: Settings → API → Create API Key",
                "note": "Copy the generated API key — you'll need it in the next step."
            },
            {
                "step": 3,
                "title": "Configure Task Force",
                "command": "Add to backend/.env:\nN8N_BASE_URL=https://your-vps.com\nN8N_API_KEY=your-api-key-here",
                "note": "Restart the backend after updating .env."
            },
            {
                "step": 4,
                "title": "Verify connection",
                "command": "GET /api/n8n/status",
                "note": "Should return {connected: true}."
            },
        ],
        "alternatives": [
            {"platform": "Railway", "cost": "Free hobby tier", "url": "https://railway.app/template/n8n"},
            {"platform": "Render", "cost": "$7/mo", "url": "https://render.com"},
            {"platform": "Any VPS", "cost": "$5/mo", "url": "Docker required"},
        ]
    }
