"""
External Agents (.tfagent) — Part 1: Upload + Validation + AST Security Scan

Safe-to-ship subset of Prompt 7:
- Accept .tfagent / .zip upload (≤ 50MB)
- Extract & validate manifest.json schema
- AST-scan every .py file for banned imports / dangerous calls
- Validate requirements.txt against ALLOWED_PACKAGES whitelist
- Store the validated package (base64-encoded zip) in MongoDB `agent_packages`

Runtime execution (per-agent venv, multi-file imports) is Part 2 — DEFERRED.
Hosting subscription tier is Part 3 — DEFERRED.

Buyers can browse external agent listings + see manifest schema + security badge
right away. They just can't EXECUTE external agents on our infra yet.
"""
import ast
import asyncio
import base64
import io
import json
import re
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from lib import external_agent_runtime as runtime

router = APIRouter()

# ─── Config ───
MAX_UPLOAD_BYTES = 50 * 1024 * 1024          # 50 MB compressed
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024   # 100 MB uncompressed (zip bomb guard)
MAX_FILES = 200

ALLOWED_PACKAGES = {
    # AI/ML
    "openai", "anthropic", "google-generativeai", "langchain", "langchain-core",
    "langchain-community", "crewai", "transformers", "sentence-transformers",
    "tiktoken", "tokenizers", "litellm", "instructor",
    # Data
    "pandas", "numpy", "pydantic", "jsonschema", "pyarrow",
    # HTTP
    "httpx", "aiohttp", "requests",
    # Parsing
    "beautifulsoup4", "lxml", "markdown", "pyyaml", "toml", "feedparser",
    # Utils
    "python-dateutil", "pytz", "regex", "jinja2", "pillow", "python-slugify",
    # DB clients
    "pymongo", "motor", "asyncpg", "redis",
    # Service SDKs
    "slack-sdk", "tweepy", "discord.py", "python-telegram-bot",
    "stripe", "notion-client", "gspread", "twilio", "sendgrid",
    "google-api-python-client",
}

BANNED_AST_CALLS = {
    "eval", "exec", "compile", "__import__",
    "os.system", "os.popen", "os.exec", "os.execv", "os.execve",
    "subprocess.run", "subprocess.call", "subprocess.Popen",
    "shutil.rmtree", "shutil.rmtree", "shutil.move", "shutil.copytree",
}

BANNED_MODULES = {
    "subprocess", "socket", "ctypes", "multiprocessing", "threading",
    "signal", "resource", "pty", "fcntl", "termios", "pickle", "shelve",
    "marshal", "builtins", "importlib", "code", "pdb", "telnetlib",
    "ftplib", "smtplib", "xmlrpc",
}

# `os` is partially allowed (env reads only) — banned imports are tracked separately.
RESTRICTED_OS_ATTRS = {"system", "popen", "exec", "execv", "execve", "fork", "remove", "rmdir", "unlink"}


REQUIRED_MANIFEST_FIELDS = ["name", "version", "display_name", "description",
                            "runtime", "entry_point", "entry_function"]


# ─── Schemas ───
class PackageSummary(BaseModel):
    package_id: str
    manifest: dict
    scan_result: dict
    size_bytes: int
    file_count: int


# ─── Helpers ───
def get_current_user():
    from server import get_current_user as _u
    return _u


def get_db():
    from server import db
    return db


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _validate_manifest(raw: dict) -> dict:
    """Strict schema check on manifest.json. Raises HTTPException(400) on failure."""
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="manifest.json must be a JSON object.")
    missing = [k for k in REQUIRED_MANIFEST_FIELDS if k not in raw]
    if missing:
        raise HTTPException(status_code=400, detail=f"manifest.json missing required fields: {missing}")
    # Basic shape checks
    if not re.match(r"^[a-z0-9][a-z0-9\-_]{1,63}$", raw.get("name", "")):
        raise HTTPException(status_code=400, detail="manifest.name must be lowercase slug (a-z, 0-9, -, _).")
    if not re.match(r"^\d+\.\d+\.\d+", raw.get("version", "")):
        raise HTTPException(status_code=400, detail="manifest.version must be semver (e.g. 1.0.0).")
    if raw.get("runtime") not in ("python3.11", "python3.12"):
        raise HTTPException(status_code=400, detail="manifest.runtime must be python3.11 or python3.12.")
    if not raw["entry_point"].endswith(".py"):
        raise HTTPException(status_code=400, detail="manifest.entry_point must be a .py file.")
    # Optional fields with sane defaults
    raw.setdefault("dependencies", [])
    raw.setdefault("required_integrations", [])
    raw.setdefault("max_execution_time_seconds", 30)
    raw.setdefault("max_memory_mb", 256)
    raw.setdefault("category", "general")
    raw.setdefault("tags", [])
    return raw


def _scan_python_ast(filename: str, source: str) -> List[str]:
    """Walk the AST of one .py file. Return list of violation strings (empty → clean)."""
    violations: List[str] = []
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as e:
        return [f"{filename}: SyntaxError on line {e.lineno}: {e.msg}"]

    for node in ast.walk(tree):
        # 1. `import banned_module` / `from banned_module import x`
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in BANNED_MODULES:
                    violations.append(f"{filename}:{node.lineno}: banned import `{alias.name}`")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in BANNED_MODULES:
                violations.append(f"{filename}:{node.lineno}: banned import `from {node.module}`")
            # Disallow `from os import system, popen, ...`
            if root == "os":
                for alias in node.names:
                    if alias.name in RESTRICTED_OS_ATTRS:
                        violations.append(f"{filename}:{node.lineno}: restricted `from os import {alias.name}`")
        # 2. `eval(...)`, `exec(...)`, etc.
        elif isinstance(node, ast.Call):
            fname = _call_name(node.func)
            if fname and fname in BANNED_AST_CALLS:
                violations.append(f"{filename}:{node.lineno}: banned call `{fname}(...)`")
            # `os.system(...)`, `os.popen(...)`, etc.
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                if node.func.value.id == "os" and node.func.attr in RESTRICTED_OS_ATTRS:
                    violations.append(f"{filename}:{node.lineno}: banned call `os.{node.func.attr}(...)`")
        # 3. dunder access — __subclasses__, __mro__, __bases__
        elif isinstance(node, ast.Attribute):
            if node.attr in {"__subclasses__", "__mro__", "__bases__", "__globals__"}:
                violations.append(f"{filename}:{node.lineno}: banned attribute `{node.attr}`")
    return violations


def _call_name(node) -> str:
    """Extract dotted function name from an ast.Call().func node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _validate_requirements(requirements_txt: str) -> tuple[List[str], List[str]]:
    """Parse requirements.txt and check every package against ALLOWED_PACKAGES.
    Returns (allowed, rejected) lists."""
    allowed, rejected = [], []
    for raw_line in requirements_txt.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        # Strip version pin: `openai>=1.40.0` → `openai`
        m = re.match(r"^([a-zA-Z0-9_\-]+)", line)
        if not m:
            rejected.append(line)
            continue
        pkg = m.group(1).lower().replace("_", "-")
        if pkg in ALLOWED_PACKAGES:
            allowed.append(pkg)
        else:
            rejected.append(pkg)
    return allowed, rejected


# ─── Routes ───
@router.post("/external-agents/upload", response_model=PackageSummary)
async def upload_external_agent(file: UploadFile = File(...), user=Depends(get_current_user())):
    """Upload + validate a .tfagent (zip) package. No runtime execution yet (Part 2)."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))

    if not file.filename or not file.filename.lower().endswith((".tfagent", ".zip")):
        raise HTTPException(status_code=400, detail="File must end in .tfagent or .zip")

    blob = await file.read()
    if len(blob) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"File too large (max {MAX_UPLOAD_BYTES // 1024 // 1024}MB).")

    # Open the zip (in memory — never touch the filesystem)
    try:
        z = zipfile.ZipFile(io.BytesIO(blob), "r")
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Not a valid zip archive.")

    names = z.namelist()
    if len(names) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Too many files (max {MAX_FILES}).")

    # Zip-bomb guard: sum of uncompressed sizes.
    uncompressed_total = sum(zi.file_size for zi in z.infolist())
    if uncompressed_total > MAX_UNCOMPRESSED_BYTES:
        raise HTTPException(status_code=400, detail="Uncompressed package exceeds 100MB.")

    # Find manifest.json (allow nested first-level folder common in zips)
    manifest_path = None
    for n in names:
        if n.endswith("manifest.json") and n.count("/") <= 1:
            manifest_path = n
            break
    if not manifest_path:
        raise HTTPException(status_code=400, detail="No manifest.json found at root or first-level folder.")

    # Path prefix (handle the case where everything lives in `agent_name/...`)
    prefix = manifest_path[:manifest_path.rfind("/") + 1] if "/" in manifest_path else ""

    # Read manifest
    try:
        manifest = _validate_manifest(json.loads(z.read(manifest_path).decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"manifest.json parse error: {e}")

    # Required: entry_point must exist
    entry_path = f"{prefix}{manifest['entry_point']}"
    if entry_path not in names:
        raise HTTPException(status_code=400, detail=f"entry_point file `{manifest['entry_point']}` not in archive.")

    # Required: requirements.txt at root (or empty)
    requirements_path = f"{prefix}requirements.txt"
    requirements_txt = ""
    if requirements_path in names:
        try:
            requirements_txt = z.read(requirements_path).decode("utf-8")
        except UnicodeDecodeError:
            requirements_txt = ""

    pkg_allowed, pkg_rejected = _validate_requirements(requirements_txt)
    if pkg_rejected:
        return PackageSummary(
            package_id="",
            manifest=manifest,
            scan_result={
                "ok": False, "verdict": "rejected",
                "rejected_packages": pkg_rejected,
                "allowed_packages": pkg_allowed,
                "violations": [],
                "message": f"Disallowed dependencies: {', '.join(pkg_rejected[:5])}. Request at support@taskforceai.com.",
            },
            size_bytes=len(blob), file_count=len(names),
        )

    # AST scan every .py file
    violations: List[str] = []
    py_files = [n for n in names if n.endswith(".py")]
    for py in py_files:
        try:
            src = z.read(py).decode("utf-8", errors="ignore")
        except Exception:
            continue
        violations.extend(_scan_python_ast(py[len(prefix):] if prefix else py, src))

    # Ensure the entry_point declares the entry_function (`async def run` etc).
    entry_src = z.read(entry_path).decode("utf-8", errors="ignore")
    entry_fn = manifest["entry_function"]
    if not re.search(rf"\b(?:async\s+def|def)\s+{re.escape(entry_fn)}\s*\(", entry_src):
        violations.append(f"{manifest['entry_point']}: entry_function `{entry_fn}` not found.")

    z.close()

    scan_result = {
        "ok": len(violations) == 0,
        "verdict": "passed" if not violations else "rejected",
        "violations": violations,
        "allowed_packages": pkg_allowed,
        "rejected_packages": [],
        "file_count": len(names),
        "py_file_count": len(py_files),
        "uncompressed_bytes": uncompressed_total,
        "scanned_at": _now_iso(),
    }

    if violations:
        return PackageSummary(
            package_id="", manifest=manifest, scan_result=scan_result,
            size_bytes=len(blob), file_count=len(names),
        )

    # Validated — persist the package as base64-encoded blob in MongoDB.
    package_id = uuid.uuid4().hex
    await db.agent_packages.insert_one({
        "id": package_id,
        "user_id": user_id,
        "user_email": user.get("email"),
        "manifest": manifest,
        "scan_result": scan_result,
        "package_b64": base64.b64encode(blob).decode("ascii"),
        "size_bytes": len(blob),
        "file_count": len(names),
        "status": "validated",
        "execution_ready": False,           # Part 2 will flip this to True
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    })
    return PackageSummary(
        package_id=package_id, manifest=manifest, scan_result=scan_result,
        size_bytes=len(blob), file_count=len(names),
    )


@router.get("/external-agents/packages")
async def list_packages(user=Depends(get_current_user())):
    """List the user's uploaded packages (most-recent first)."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    cursor = db.agent_packages.find(
        {"user_id": user_id}, {"package_b64": 0, "_id": 0}
    ).sort("created_at", -1).limit(50)
    items = await cursor.to_list(50)
    return {"packages": items}


@router.get("/external-agents/packages/{package_id}")
async def get_package(package_id: str, user=Depends(get_current_user())):
    """Fetch metadata for a single uploaded package (no blob)."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    doc = await db.agent_packages.find_one(
        {"id": package_id, "user_id": user_id}, {"package_b64": 0, "_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Package not found.")
    return doc


@router.delete("/external-agents/packages/{package_id}")
async def delete_package(package_id: str, user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    res = await db.agent_packages.delete_one({"id": package_id, "user_id": user_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Package not found.")
    # Best-effort cleanup of the on-disk venv + extracted code.
    try:
        runtime.uninstall_agent(package_id)
    except Exception:
        pass
    return {"ok": True, "deleted": package_id}


@router.get("/external-agents/whitelist")
async def get_whitelist():
    """Public — surfaces the allowed packages + banned modules for documentation."""
    return {
        "allowed_packages": sorted(ALLOWED_PACKAGES),
        "banned_modules": sorted(BANNED_MODULES),
        "max_upload_mb": MAX_UPLOAD_BYTES // 1024 // 1024,
        "max_uncompressed_mb": MAX_UNCOMPRESSED_BYTES // 1024 // 1024,
        "manifest_required_fields": REQUIRED_MANIFEST_FIELDS,
    }


# ───────── Part 2: Install / Run / Runs ─────────
class RunBody(BaseModel):
    input: Optional[Any] = None
    keys: Optional[dict] = None  # user-provided BYOK overrides for this single run


async def _load_pkg_or_404(db, package_id: str, user_id: str) -> dict:
    doc = await db.agent_packages.find_one({"id": package_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Package not found.")
    return doc


@router.post("/external-agents/packages/{package_id}/install")
async def install_package(package_id: str, user=Depends(get_current_user())):
    """Kick off venv creation + pip install in the background. Idempotent —
    if the package is already installing/ready, returns the current status."""
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    doc = await _load_pkg_or_404(db, package_id, user_id)
    if doc.get("install_status") == "installing":
        return {"queued": False, "install_status": "installing",
                "message": "Install already in progress."}
    if doc.get("install_status") == "ready" and doc.get("execution_ready"):
        return {"queued": False, "install_status": "ready",
                "message": "Already installed.", "log_tail": (doc.get("install_log") or "")[-2000:]}

    # Fire-and-forget — runtime.install_agent flips status to "installing" first
    # thing, so subsequent polls see the right state.
    asyncio.create_task(runtime.install_agent(db, package_id, ALLOWED_PACKAGES))
    return {"queued": True, "install_status": "installing"}


@router.get("/external-agents/packages/{package_id}/install-status")
async def get_install_status(package_id: str, user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    doc = await _load_pkg_or_404(db, package_id, user_id)
    return runtime.install_status(doc)


@router.post("/external-agents/packages/{package_id}/run")
async def run_package(package_id: str, body: RunBody, user=Depends(get_current_user())):
    """Execute the installed agent. Charges credits via the dual-pool wallet."""
    from lib import credit_wallet
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    doc = await _load_pkg_or_404(db, package_id, user_id)
    if not doc.get("execution_ready") or doc.get("install_status") != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"Agent not ready (install_status={doc.get('install_status') or 'not_installed'}). "
                   "Run the install endpoint first.",
        )

    # Affordability check BEFORE running so we never burn compute on insolvent accounts.
    afford = await credit_wallet.can_afford(db, user, "external_agent_run")
    if not afford.get("allowed"):
        raise HTTPException(status_code=402, detail={
            "error": "INSUFFICIENT_CREDITS",
            "needed": afford.get("cost"),
            "balance": afford.get("balance"),
            "message": "Top up credits or upgrade your plan to run external agents.",
        })

    manifest = doc.get("manifest") or {}
    entry_path = manifest.get("entry_point") or "main.py"
    entry_fn = manifest.get("entry_function") or "run"

    # Resolve user BYOK keys: stored vault keys + per-call overrides.
    # We pull the simple `byok_keys` field if present; the heavy KMS-decrypt path
    # lives elsewhere and is out of scope here.
    stored_keys = (await db.users.find_one(
        {"$or": [{"id": user_id}, {"email": user.get("email")}]},
        {"byok_keys": 1, "_id": 0},
    ) or {}).get("byok_keys") or {}
    keys = {**stored_keys, **(body.keys or {})}

    timeout_s = int(manifest.get("max_execution_time_seconds") or 30)
    memory_mb = int(manifest.get("max_memory_mb") or 256)

    run_id = uuid.uuid4().hex
    started_at = _now_iso()
    result = await runtime.run_agent(
        package_id=package_id,
        entry_path_rel=entry_path,
        entry_fn=entry_fn,
        input_data=body.input if body.input is not None else {},
        env_vars={},  # ENV pass-through can be added once manifest supports it
        user_api_keys=keys,
        timeout_seconds=timeout_s,
        memory_mb=memory_mb,
    )

    # Charge credits AFTER execution so failures don't double-deduct via retries.
    # (Real-world tradeoff: a successful but very long run is still billed once.)
    debit = await credit_wallet.debit(db, user, "external_agent_run", ref=run_id)

    run_doc = {
        "id": run_id,
        "package_id": package_id,
        "user_id": user_id,
        "user_email": user.get("email"),
        "started_at": started_at,
        "finished_at": _now_iso(),
        "duration_ms": result.get("duration_ms") or 0,
        "success": bool(result.get("success")),
        "status": "success" if result.get("success") else "failed",
        "input": body.input if body.input is not None else {},
        "result": result.get("result"),
        "output": result.get("output") or "",
        "stderr": result.get("stderr") or "",
        "error": result.get("error"),
        "trace": result.get("trace"),
        "exit_code": result.get("exit_code"),
        "credits_spent": int(debit.get("cost") or 0),
    }
    await db.external_agent_runs.insert_one(run_doc)
    await db.agent_packages.update_one(
        {"id": package_id, "user_id": user_id},
        {"$inc": {"usage.run_count": 1, "usage.failures": 0 if result.get("success") else 1},
         "$set": {"usage.last_run_at": _now_iso(), "updated_at": _now_iso()}},
    )
    # Strip the heavy `_id` before returning.
    run_doc.pop("_id", None)
    run_doc["credits_remaining"] = debit.get("balance")
    return run_doc


@router.get("/external-agents/packages/{package_id}/runs")
async def list_runs(package_id: str, limit: int = 25, user=Depends(get_current_user())):
    db = get_db()
    user_id = str(user.get("id", user.get("email")))
    await _load_pkg_or_404(db, package_id, user_id)  # 404 if not owned
    cursor = db.external_agent_runs.find(
        {"package_id": package_id, "user_id": user_id}, {"_id": 0}
    ).sort("started_at", -1).limit(max(1, min(int(limit), 100)))
    items = await cursor.to_list(length=100)
    return {"runs": items}
