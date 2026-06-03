"""
External Agent Runtime — Prompt 7 Part 2

Manages the lifecycle of validated `.tfagent` packages beyond storage:
    1. EXTRACT — unzip the stored blob to /app/data/agent_venvs/{package_id}/code/
    2. INSTALL — create an isolated venv + `pip install -r requirements.txt`
                 using ONLY the whitelisted packages declared by manifest.
    3. RUN     — spawn a subprocess in the venv that invokes the agent's
                 entry_function with a JSON payload (input, env, keys), under
                 a hard wallclock timeout + memory rlimit.

Security:
    - Packages are AST-scanned at upload (external_agents.upload). Any package
      reaching INSTALL is already screened for banned modules/calls.
    - pip is invoked with `--no-build-isolation --no-input` and the requirements
      file is regenerated from manifest.dependencies (re-validated against the
      same ALLOWED_PACKAGES whitelist) — we NEVER trust the on-disk requirements.txt
      blindly even though the AST scan vetted it.
    - Subprocess uses preexec_fn to set RLIMIT_AS (memory) and RLIMIT_CPU.
    - Wallclock timeout via subprocess.communicate(timeout=N) + process-group kill.
    - The harness in /app/backend/lib/agent_runner_harness.py is the only code
      path that loads the user's entry module — never imported into our own process.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import re
import resource
import shutil
import signal
import subprocess
import sys
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ───────── Config ─────────
DATA_ROOT = Path(os.environ.get("AGENT_DATA_ROOT") or "/app/data/agent_venvs")
DATA_ROOT.mkdir(parents=True, exist_ok=True)

HARNESS_SRC = Path(__file__).parent / "agent_runner_harness.py"

# Wallclock hard cap regardless of manifest setting.
MAX_RUN_SECONDS = 60
MIN_RUN_SECONDS = 1
# Memory rlimit hard cap (bytes); manifest.max_memory_mb is capped to this.
MAX_MEMORY_MB = 512
MIN_MEMORY_MB = 64

# pip install hard cap so misbehaving packages can't stall the queue forever.
PIP_INSTALL_TIMEOUT_S = 240

# Sentinel for parsing harness output.
RESULT_SENTINEL = "___TFAI_RESULT___"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_pkg_id(package_id: str) -> str:
    """Defence-in-depth — package_id is a hex uuid but normalize anyway."""
    if not package_id or not re.match(r"^[a-f0-9]{8,64}$", package_id):
        raise ValueError("invalid package_id")
    return package_id


def package_dir(package_id: str) -> Path:
    return DATA_ROOT / _safe_pkg_id(package_id)


def code_dir(package_id: str) -> Path:
    return package_dir(package_id) / "code"


def venv_dir(package_id: str) -> Path:
    return package_dir(package_id) / "venv"


def venv_python(package_id: str) -> Path:
    return venv_dir(package_id) / "bin" / "python"


def venv_pip(package_id: str) -> Path:
    return venv_dir(package_id) / "bin" / "pip"


def harness_path(package_id: str) -> Path:
    return package_dir(package_id) / "_runner.py"


# ───────── Extract ─────────
def _extract_blob(package_b64: str, dest: Path) -> Tuple[str, str]:
    """Extract the persisted zip blob to `dest`. Returns (manifest_path, code_prefix)
    where code_prefix is the in-zip folder containing manifest.json (may be empty)."""
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)
    blob = base64.b64decode(package_b64)
    with zipfile.ZipFile(io.BytesIO(blob), "r") as z:
        names = z.namelist()
        manifest_in_zip = next(
            (n for n in names if n.endswith("manifest.json") and n.count("/") <= 1),
            None,
        )
        if not manifest_in_zip:
            raise RuntimeError("manifest.json missing from stored blob")
        prefix = manifest_in_zip[: manifest_in_zip.rfind("/") + 1] if "/" in manifest_in_zip else ""
        for n in names:
            # Skip directory entries
            if n.endswith("/"):
                continue
            # Strip the prefix so the agent's files land directly under `dest`.
            rel = n[len(prefix):] if prefix and n.startswith(prefix) else n
            if not rel or rel.startswith("/") or ".." in rel:
                continue
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            with z.open(n) as src, open(out, "wb") as fp:
                shutil.copyfileobj(src, fp)
        return manifest_in_zip, prefix


# ───────── Install ─────────
def _write_pinned_requirements(deps: List[str], target: Path, allowed: set[str]) -> List[str]:
    """Regenerate requirements.txt from manifest.dependencies — re-validating each
    line against the global whitelist. Returns the list of actually written lines."""
    written = []
    bad = []
    for raw in deps or []:
        if not isinstance(raw, str):
            continue
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([a-zA-Z0-9_\-]+)", line)
        if not m:
            bad.append(line)
            continue
        pkg = m.group(1).lower().replace("_", "-")
        if pkg not in allowed:
            bad.append(line)
            continue
        written.append(line)
    if bad:
        raise RuntimeError(f"disallowed dependencies (re-validation): {bad[:5]}")
    target.write_text("\n".join(written) + ("\n" if written else ""))
    return written


def _drop_harness(package_id: str) -> None:
    """Copy the runner harness into the package directory."""
    dst = harness_path(package_id)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(HARNESS_SRC, dst)


def _create_venv(package_id: str) -> str:
    """Create a fresh venv. Returns the path. Raises on failure."""
    vdir = venv_dir(package_id)
    if vdir.exists():
        shutil.rmtree(vdir, ignore_errors=True)
    # Use the running interpreter to bootstrap the venv (python3.11 in our container).
    cmd = [sys.executable, "-m", "venv", "--clear", str(vdir)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(f"venv creation failed: {proc.stderr[:500]}")
    return str(vdir)


def _pip_install(package_id: str, requirements_path: Path) -> str:
    """Run pip install -r requirements inside the venv. Returns combined log
    (capped to 50KB). Raises on non-zero exit."""
    pip = venv_pip(package_id)
    if not pip.exists():
        raise RuntimeError("venv pip not found — venv creation likely failed")
    # If requirements is empty, skip the install entirely.
    if not requirements_path.exists() or not requirements_path.read_text().strip():
        return "(no dependencies declared — venv ready)"
    cmd = [
        str(pip), "install",
        "--no-input",
        "--disable-pip-version-check",
        "--no-color",
        "-r", str(requirements_path),
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=PIP_INSTALL_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"pip install timed out after {PIP_INSTALL_TIMEOUT_S}s")
    log = ((proc.stdout or "") + "\n" + (proc.stderr or ""))[:50_000]
    if proc.returncode != 0:
        raise RuntimeError(f"pip install failed (exit {proc.returncode}):\n{log[-2000:]}")
    return log


async def install_agent(db, package_id: str, allowed_packages: set[str]) -> Dict[str, Any]:
    """End-to-end install: extract → venv → pip → harness. Mutates the
    `agent_packages` row in-place and returns the updated install record."""
    doc = await db.agent_packages.find_one({"id": package_id})
    if not doc:
        raise RuntimeError("package not found")
    if doc.get("install_status") == "installing":
        return {"ok": False, "install_status": "installing", "message": "install already in progress"}

    # Mark as installing first so concurrent triggers no-op.
    await db.agent_packages.update_one(
        {"id": package_id},
        {"$set": {"install_status": "installing", "install_started_at": _now_iso(),
                  "install_error": None, "updated_at": _now_iso()}},
    )

    try:
        manifest = doc.get("manifest") or {}
        deps = manifest.get("dependencies") or []
        cdir = code_dir(package_id)
        _extract_blob(doc["package_b64"], cdir)
        req_path = cdir / "requirements.txt"
        written = _write_pinned_requirements(deps, req_path, allowed_packages)
        _create_venv(package_id)
        log = _pip_install(package_id, req_path)
        _drop_harness(package_id)
        await db.agent_packages.update_one(
            {"id": package_id},
            {"$set": {
                "install_status": "ready",
                "execution_ready": True,
                "installed_at": _now_iso(),
                "install_log": log,
                "install_deps_pinned": written,
                "extracted_path": str(cdir),
                "venv_path": str(venv_dir(package_id)),
                "install_error": None,
                "updated_at": _now_iso(),
            }},
        )
        return {"ok": True, "install_status": "ready", "log": log, "deps": written}
    except Exception as e:
        await db.agent_packages.update_one(
            {"id": package_id},
            {"$set": {
                "install_status": "failed",
                "execution_ready": False,
                "install_error": str(e)[:2000],
                "updated_at": _now_iso(),
            }},
        )
        return {"ok": False, "install_status": "failed", "error": str(e)[:2000]}


def install_status(db_doc: dict) -> Dict[str, Any]:
    """Snapshot the install state of a package (for the polling endpoint)."""
    return {
        "package_id": db_doc.get("id"),
        "install_status": db_doc.get("install_status") or "not_installed",
        "execution_ready": bool(db_doc.get("execution_ready")),
        "installed_at": db_doc.get("installed_at"),
        "install_error": db_doc.get("install_error"),
        "install_log_tail": (db_doc.get("install_log") or "")[-4000:],
        "deps_pinned": db_doc.get("install_deps_pinned") or [],
    }


# ───────── Run ─────────
def _preexec_factory(memory_mb: int, cpu_seconds: int):
    """Returns a preexec_fn that sets rlimits in the child before exec.
    Skipped on platforms where setrlimit is unsupported (won't happen in K8s linux)."""
    mem_bytes = memory_mb * 1024 * 1024

    def _apply() -> None:
        try:
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        except (ValueError, OSError):
            pass
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
        except (ValueError, OSError):
            pass
        # Start the child in its own process group so we can kill descendants.
        try:
            os.setsid()
        except OSError:
            pass
    return _apply


def _parse_harness_output(stdout: str) -> Tuple[Optional[dict], str]:
    """Find the harness sentinel and pull out the result JSON.
    Returns (parsed_dict, prefix_stdout)."""
    idx = stdout.rfind(RESULT_SENTINEL)
    if idx < 0:
        return None, stdout
    prefix = stdout[:idx].rstrip()
    tail = stdout[idx + len(RESULT_SENTINEL):]
    try:
        return json.loads(tail), prefix
    except json.JSONDecodeError:
        return None, stdout


def run_agent_sync(
    package_id: str,
    entry_path_rel: str,
    entry_fn: str,
    input_data: Any,
    env_vars: Dict[str, str],
    user_api_keys: Dict[str, str],
    timeout_seconds: int,
    memory_mb: int,
) -> Dict[str, Any]:
    """Synchronous subprocess execution. Returns a structured result dict
    suitable for persistence in `external_agent_runs`.

    NOTE: This is the in-process synchronous worker. Callers running in
    asyncio should wrap with `asyncio.to_thread(...)` (see `run_agent`)."""
    pkg = package_dir(package_id)
    cdir = code_dir(package_id)
    py = venv_python(package_id)
    harness = harness_path(package_id)

    if not py.exists() or not harness.exists() or not cdir.exists():
        return {"success": False, "error": "agent not installed", "output": "", "result": None,
                "duration_ms": 0, "exit_code": None}

    entry_abs = cdir / entry_path_rel
    if not entry_abs.is_file():
        return {"success": False, "error": f"entry_point file missing: {entry_path_rel}",
                "output": "", "result": None, "duration_ms": 0, "exit_code": None}

    timeout_seconds = max(MIN_RUN_SECONDS, min(int(timeout_seconds or 30), MAX_RUN_SECONDS))
    memory_mb = max(MIN_MEMORY_MB, min(int(memory_mb or 256), MAX_MEMORY_MB))

    payload = json.dumps({
        "entry_path": str(entry_abs),
        "entry_fn": entry_fn,
        "input": input_data if input_data is not None else {},
        "env": env_vars or {},
        "keys": user_api_keys or {},
    })

    t0 = time.monotonic()
    proc = subprocess.Popen(
        [str(py), str(harness)],
        cwd=str(cdir),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
        preexec_fn=_preexec_factory(memory_mb, timeout_seconds),
        env={  # Minimal env — keep host secrets out of agent reach.
            "PATH": f"{venv_dir(package_id) / 'bin'}:/usr/local/bin:/usr/bin:/bin",
            "HOME": str(pkg),
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    try:
        stdout, stderr = proc.communicate(input=payload, timeout=timeout_seconds)
        timed_out = False
    except subprocess.TimeoutExpired:
        # Kill the entire process group (the child may have spawned subprocs,
        # though AST scan should have prevented that).
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        stdout, stderr = proc.communicate()
        timed_out = True
    duration_ms = int((time.monotonic() - t0) * 1000)

    if timed_out:
        return {"success": False, "error": f"agent execution timed out after {timeout_seconds}s",
                "output": (stdout or "")[:8000], "stderr": (stderr or "")[:4000],
                "result": None, "duration_ms": duration_ms, "exit_code": -9}

    parsed, prefix = _parse_harness_output(stdout or "")
    if parsed is None:
        # No sentinel — runtime crashed before producing structured output.
        return {
            "success": False,
            "error": "no result emitted (agent crashed before completion)",
            "output": (stdout or "")[:8000],
            "stderr": (stderr or "")[:4000],
            "result": None,
            "duration_ms": duration_ms,
            "exit_code": proc.returncode,
        }
    if not parsed.get("ok"):
        return {
            "success": False,
            "error": parsed.get("error") or "unknown agent error",
            "trace": parsed.get("trace"),
            "output": prefix[:8000],
            "stderr": (stderr or "")[:4000],
            "result": None,
            "duration_ms": duration_ms,
            "exit_code": proc.returncode,
        }
    return {
        "success": True,
        "error": None,
        "output": prefix[:8000],
        "stderr": (stderr or "")[:4000],
        "result": parsed.get("result"),
        "duration_ms": duration_ms,
        "exit_code": proc.returncode,
    }


async def run_agent(
    package_id: str,
    entry_path_rel: str,
    entry_fn: str,
    input_data: Any,
    env_vars: Dict[str, str],
    user_api_keys: Dict[str, str],
    timeout_seconds: int,
    memory_mb: int,
) -> Dict[str, Any]:
    """Async wrapper — offloads the blocking subprocess to a worker thread."""
    return await asyncio.to_thread(
        run_agent_sync,
        package_id, entry_path_rel, entry_fn, input_data,
        env_vars, user_api_keys, timeout_seconds, memory_mb,
    )


def uninstall_agent(package_id: str) -> None:
    """Remove the venv and extracted code (called on package delete)."""
    pdir = package_dir(package_id)
    if pdir.exists():
        shutil.rmtree(pdir, ignore_errors=True)


__all__ = [
    "install_agent", "install_status", "run_agent", "run_agent_sync",
    "uninstall_agent", "package_dir", "code_dir", "venv_dir",
    "DATA_ROOT", "MAX_MEMORY_MB", "MAX_RUN_SECONDS",
]
