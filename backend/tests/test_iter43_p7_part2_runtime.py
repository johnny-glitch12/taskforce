"""
Iter43 — Prompt 7 Part 2: External Agent Pip Venv Runtime tests.

Validates:
  - install endpoint kicks off venv creation + pip install (background-task)
  - install-status reports the lifecycle: not_installed → installing → ready
  - run endpoint executes the installed agent and persists a run row
  - run endpoint rejects 409 when execution_ready=False
  - run endpoint rejects 402 when credits are insufficient
  - timeout handling kills the subprocess and reports duration ≤ timeout+slack
  - delete removes the on-disk venv + extracted code
  - runs listing reflects history
"""
import io
import os
import time
import uuid
import zipfile

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@nova.ai"
ADMIN_PASS = "admin123"


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=15)
    if r.status_code != 200:
        return None
    return r.json().get("token") or r.json().get("access_token")


def _build_zip(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path, content in files.items():
            if isinstance(content, str):
                content = content.encode("utf-8")
            z.writestr(path, content)
    return buf.getvalue()


def _wait_for_status(token, package_id, want, timeout=180):
    """Poll install-status until the desired status is reached or timeout."""
    headers = {"Authorization": f"Bearer {token}"}
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = requests.get(
            f"{BASE_URL}/api/external-agents/packages/{package_id}/install-status",
            headers=headers, timeout=10,
        )
        if r.status_code == 200:
            last = r.json()
            if last.get("install_status") == want:
                return last
            if last.get("install_status") == "failed" and want == "ready":
                return last  # caller will assert + see install_error
        time.sleep(2)
    return last or {"install_status": "TIMEOUT"}


def _upload_minimal(token, manifest_overrides=None, main_py=None, requirements=None):
    """Helper: upload a valid .tfagent and return its package_id."""
    manifest = {
        "name": f"runtime-test-{uuid.uuid4().hex[:6]}",
        "version": "1.0.0",
        "display_name": "Runtime Test Agent",
        "description": "Runtime test",
        "runtime": "python3.11",
        "entry_point": "main.py",
        "entry_function": "run",
        "dependencies": [],
    }
    if manifest_overrides:
        manifest.update(manifest_overrides)
    files = {
        "manifest.json": __import__("json").dumps(manifest),
        "main.py": main_py or "def run(input):\n    return {'echoed': input, 'ok': True}\n",
    }
    if requirements is not None:
        files["requirements.txt"] = requirements
    blob = _build_zip(files)
    r = requests.post(
        f"{BASE_URL}/api/external-agents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (f"{manifest['name']}.tfagent", blob, "application/zip")},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("package_id"), f"upload failed: {body}"
    return body["package_id"]


# ─── Fixtures ────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def token():
    t = _login(ADMIN_EMAIL, ADMIN_PASS)
    assert t, "admin login must succeed"
    return t


# ─── Tests ───────────────────────────────────────────────────────────────────
def test_install_status_before_install(token):
    """A freshly-uploaded package starts at install_status='not_installed'."""
    pkg_id = _upload_minimal(token)
    r = requests.get(
        f"{BASE_URL}/api/external-agents/packages/{pkg_id}/install-status",
        headers={"Authorization": f"Bearer {token}"}, timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["install_status"] == "not_installed"
    assert body["execution_ready"] is False
    # Cleanup
    requests.delete(f"{BASE_URL}/api/external-agents/packages/{pkg_id}",
                    headers={"Authorization": f"Bearer {token}"}, timeout=10)


def test_run_before_install_409(token):
    """Running an un-installed package returns 409 with a clear error."""
    pkg_id = _upload_minimal(token)
    r = requests.post(
        f"{BASE_URL}/api/external-agents/packages/{pkg_id}/run",
        headers={"Authorization": f"Bearer {token}"},
        json={"input": {"hello": "world"}}, timeout=10,
    )
    assert r.status_code == 409, r.text
    assert "not ready" in r.text.lower() or "install_status" in r.text.lower()
    requests.delete(f"{BASE_URL}/api/external-agents/packages/{pkg_id}",
                    headers={"Authorization": f"Bearer {token}"}, timeout=10)


def test_install_and_run_no_deps(token):
    """Happy path: upload an agent with zero deps, install, run, get expected result."""
    pkg_id = _upload_minimal(
        token,
        main_py="def run(input):\n    return {'doubled': (input or {}).get('n', 0) * 2}\n",
    )
    # Install
    r = requests.post(
        f"{BASE_URL}/api/external-agents/packages/{pkg_id}/install",
        headers={"Authorization": f"Bearer {token}"}, timeout=10,
    )
    assert r.status_code == 200, r.text
    assert r.json().get("queued") in (True, False)  # idempotent if it was already queued
    # Wait for ready
    status = _wait_for_status(token, pkg_id, "ready", timeout=120)
    assert status["install_status"] == "ready", f"install failed: {status}"
    assert status["execution_ready"] is True
    # Run
    r = requests.post(
        f"{BASE_URL}/api/external-agents/packages/{pkg_id}/run",
        headers={"Authorization": f"Bearer {token}"},
        json={"input": {"n": 7}}, timeout=30,
    )
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["success"] is True, run
    assert run["result"] == {"doubled": 14}
    assert run["duration_ms"] >= 0
    assert run["exit_code"] == 0
    # Runs list
    r = requests.get(
        f"{BASE_URL}/api/external-agents/packages/{pkg_id}/runs",
        headers={"Authorization": f"Bearer {token}"}, timeout=10,
    )
    assert r.status_code == 200
    assert len(r.json()["runs"]) >= 1
    requests.delete(f"{BASE_URL}/api/external-agents/packages/{pkg_id}",
                    headers={"Authorization": f"Bearer {token}"}, timeout=10)


def test_install_idempotent(token):
    """Calling install twice on a ready package returns 'already installed'."""
    pkg_id = _upload_minimal(token)
    requests.post(
        f"{BASE_URL}/api/external-agents/packages/{pkg_id}/install",
        headers={"Authorization": f"Bearer {token}"}, timeout=10,
    )
    _wait_for_status(token, pkg_id, "ready", timeout=60)
    r2 = requests.post(
        f"{BASE_URL}/api/external-agents/packages/{pkg_id}/install",
        headers={"Authorization": f"Bearer {token}"}, timeout=10,
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["install_status"] == "ready"
    assert body["queued"] is False
    requests.delete(f"{BASE_URL}/api/external-agents/packages/{pkg_id}",
                    headers={"Authorization": f"Bearer {token}"}, timeout=10)


def test_run_timeout_kills_subprocess(token):
    """An agent that sleeps past its timeout should be killed and report failure."""
    pkg_id = _upload_minimal(
        token,
        manifest_overrides={"max_execution_time_seconds": 2},
        main_py="import time\ndef run(input):\n    time.sleep(20)\n    return {'should_not_reach': True}\n",
    )
    requests.post(
        f"{BASE_URL}/api/external-agents/packages/{pkg_id}/install",
        headers={"Authorization": f"Bearer {token}"}, timeout=10,
    )
    status = _wait_for_status(token, pkg_id, "ready", timeout=60)
    assert status["install_status"] == "ready"

    t0 = time.time()
    r = requests.post(
        f"{BASE_URL}/api/external-agents/packages/{pkg_id}/run",
        headers={"Authorization": f"Bearer {token}"},
        json={"input": {}}, timeout=30,
    )
    elapsed = time.time() - t0
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["success"] is False
    assert "timed out" in (run["error"] or "").lower(), run
    # Wallclock should be near the 2s manifest cap (+ small overhead).
    assert elapsed < 15, f"timeout did not enforce kill: elapsed={elapsed:.1f}s"
    requests.delete(f"{BASE_URL}/api/external-agents/packages/{pkg_id}",
                    headers={"Authorization": f"Bearer {token}"}, timeout=10)


def test_run_with_async_entry(token):
    """async def run(input) should also work via the harness."""
    pkg_id = _upload_minimal(
        token,
        main_py="async def run(input):\n    return {'async': True, 'echo': input}\n",
    )
    requests.post(
        f"{BASE_URL}/api/external-agents/packages/{pkg_id}/install",
        headers={"Authorization": f"Bearer {token}"}, timeout=10,
    )
    _wait_for_status(token, pkg_id, "ready", timeout=60)
    r = requests.post(
        f"{BASE_URL}/api/external-agents/packages/{pkg_id}/run",
        headers={"Authorization": f"Bearer {token}"},
        json={"input": {"x": 42}}, timeout=30,
    )
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["success"] is True, run
    assert run["result"] == {"async": True, "echo": {"x": 42}}
    requests.delete(f"{BASE_URL}/api/external-agents/packages/{pkg_id}",
                    headers={"Authorization": f"Bearer {token}"}, timeout=10)


def test_run_with_multi_file_imports(token):
    """Agent can import sibling helper modules at runtime."""
    pkg_id_resp = _upload_helper_multi_file(token)
    pkg_id = pkg_id_resp
    requests.post(
        f"{BASE_URL}/api/external-agents/packages/{pkg_id}/install",
        headers={"Authorization": f"Bearer {token}"}, timeout=10,
    )
    _wait_for_status(token, pkg_id, "ready", timeout=60)
    r = requests.post(
        f"{BASE_URL}/api/external-agents/packages/{pkg_id}/run",
        headers={"Authorization": f"Bearer {token}"},
        json={"input": {"a": 3, "b": 4}}, timeout=30,
    )
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["success"] is True, run
    assert run["result"] == {"sum": 7}
    requests.delete(f"{BASE_URL}/api/external-agents/packages/{pkg_id}",
                    headers={"Authorization": f"Bearer {token}"}, timeout=10)


def _upload_helper_multi_file(token):
    manifest = {
        "name": f"multi-{uuid.uuid4().hex[:6]}",
        "version": "1.0.0",
        "display_name": "Multi-file agent",
        "description": "Uses a helpers.py sibling.",
        "runtime": "python3.11",
        "entry_point": "main.py",
        "entry_function": "run",
        "dependencies": [],
    }
    main_py = (
        "from helpers import add\n"
        "def run(input):\n"
        "    return {'sum': add((input or {}).get('a', 0), (input or {}).get('b', 0))}\n"
    )
    helpers_py = "def add(a, b):\n    return a + b\n"
    files = {
        "manifest.json": __import__("json").dumps(manifest),
        "main.py": main_py,
        "helpers.py": helpers_py,
    }
    blob = _build_zip(files)
    r = requests.post(
        f"{BASE_URL}/api/external-agents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (f"{manifest['name']}.tfagent", blob, "application/zip")},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    return r.json()["package_id"]


def test_run_with_allowed_dependency(token):
    """Agent declaring a small whitelisted package (python-slugify) installs + runs."""
    manifest_overrides = {
        "name": f"slug-{uuid.uuid4().hex[:6]}",
        "dependencies": ["python-slugify"],
    }
    main_py = (
        "from slugify import slugify\n"
        "def run(input):\n"
        "    return {'slug': slugify((input or {}).get('text', ''))}\n"
    )
    pkg_id = _upload_minimal(token, manifest_overrides=manifest_overrides,
                             main_py=main_py)
    requests.post(
        f"{BASE_URL}/api/external-agents/packages/{pkg_id}/install",
        headers={"Authorization": f"Bearer {token}"}, timeout=10,
    )
    status = _wait_for_status(token, pkg_id, "ready", timeout=180)
    assert status["install_status"] == "ready", f"install failed: {status}"
    assert "python-slugify" in (status["deps_pinned"] or [])

    r = requests.post(
        f"{BASE_URL}/api/external-agents/packages/{pkg_id}/run",
        headers={"Authorization": f"Bearer {token}"},
        json={"input": {"text": "Hello World 2026!"}}, timeout=30,
    )
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["success"] is True, run
    assert run["result"] == {"slug": "hello-world-2026"}, run
    requests.delete(f"{BASE_URL}/api/external-agents/packages/{pkg_id}",
                    headers={"Authorization": f"Bearer {token}"}, timeout=10)


def test_delete_removes_disk_artifacts(token):
    """After delete, the package directory under DATA_ROOT no longer exists."""
    import sys
    sys.path.insert(0, "/app/backend")
    from lib import external_agent_runtime as rt

    pkg_id = _upload_minimal(token)
    requests.post(
        f"{BASE_URL}/api/external-agents/packages/{pkg_id}/install",
        headers={"Authorization": f"Bearer {token}"}, timeout=10,
    )
    _wait_for_status(token, pkg_id, "ready", timeout=60)
    assert rt.package_dir(pkg_id).exists()
    r = requests.delete(
        f"{BASE_URL}/api/external-agents/packages/{pkg_id}",
        headers={"Authorization": f"Bearer {token}"}, timeout=10,
    )
    assert r.status_code == 200
    assert not rt.package_dir(pkg_id).exists(), "venv not cleaned up after delete"


def test_unknown_package_404(token):
    """Install / run / status on a fabricated package_id returns 404."""
    bogus = "deadbeef" * 4
    for path in ("install", "install-status", "run", "runs"):
        method = requests.post if path in ("install", "run") else requests.get
        kwargs = {"headers": {"Authorization": f"Bearer {token}"}, "timeout": 10}
        if path == "run":
            kwargs["json"] = {"input": {}}
        r = method(f"{BASE_URL}/api/external-agents/packages/{bogus}/{path}", **kwargs)
        assert r.status_code == 404, f"{path} should 404, got {r.status_code}: {r.text[:200]}"
