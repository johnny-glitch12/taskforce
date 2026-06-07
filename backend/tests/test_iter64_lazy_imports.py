"""
Prompt 23 regression — verify that all Supabase-dependent route modules
import cleanly when SUPABASE_URL / SUPABASE_KEY are unset.

This was the Railway boot-crash. Each module used to call
`create_client(None, None)` at top-level and the whole app died.

This test runs in a SUBPROCESS with a scrubbed environment so the parent
test runner doesn't leak its dev .env values.
"""
import subprocess
import sys
import textwrap


def _run_in_clean_env(snippet: str):
    """Run snippet in a subprocess where load_dotenv is neutralised and
    every optional service env var has been popped."""
    code = textwrap.dedent("""
        import sys
        # Block load_dotenv so the backend/.env file can't sneak in values
        import dotenv as _d
        _d.load_dotenv = lambda *a, **kw: False

        import os
        for k in (
            'SUPABASE_URL','SUPABASE_KEY','SUPABASE_SERVICE_ROLE_KEY',
            'STRIPE_API_KEY','STRIPE_SECRET_KEY','RESEND_API_KEY',
            'CELERY_BROKER_URL','REDIS_URL','EMERGENT_LLM_KEY',
            'GOOGLE_API_KEY','OPENAI_API_KEY','GEMINI_API_KEY',
            'ANTHROPIC_API_KEY','FERNET_KEY','AWS_ACCESS_KEY_ID',
        ):
            os.environ.pop(k, None)

        # Minimal required env to satisfy server.py at import time.
        os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
        os.environ.setdefault('JWT_SECRET', 'iter64-test-secret-only')
        os.environ.setdefault('DB_NAME', 'iter64_test')

    """) + snippet
    r = subprocess.run(
        [sys.executable, "-c", code],
        cwd="/app/backend",
        capture_output=True, text=True, timeout=45,
    )
    return r


def test_routes_security_lazy_supabase_returns_none():
    """When SUPABASE_URL is unset, security.get_supabase() returns None.
    Importing through server (realistic Railway boot order) avoids the
    artificial circular-import that hits when route modules are imported
    standalone."""
    r = _run_in_clean_env(
        "import server\n"
        "from routes import security\n"
        "print('SB=' + ('None' if security.get_supabase() is None else 'CONNECTED'))"
    )
    assert r.returncode == 0, f"crash: {r.stdout}{r.stderr}"
    assert "SB=None" in r.stdout, f"get_supabase() should return None when unset: {r.stdout}"


def test_routes_published_lazy_supabase_returns_none():
    r = _run_in_clean_env(
        "import server\n"
        "from routes import published\n"
        "print('SB=' + ('None' if published.get_supabase() is None else 'CONNECTED'))"
    )
    assert r.returncode == 0, f"crash: {r.stdout}{r.stderr}"
    assert "SB=None" in r.stdout


def test_routes_agent_lazy_supabase_returns_none():
    r = _run_in_clean_env(
        "import server\n"
        "from routes import agent\n"
        "print('SB=' + ('None' if agent.get_supabase() is None else 'CONNECTED'))"
    )
    assert r.returncode == 0, f"crash: {r.stdout}{r.stderr}"
    assert "SB=None" in r.stdout


def test_server_imports_without_optional_env():
    """The whole server module must import with only MONGO_URL + JWT_SECRET."""
    r = _run_in_clean_env("import server; print('SERVER_OK')")
    assert r.returncode == 0, f"server import crashed:\nstdout={r.stdout}\nstderr={r.stderr}"
    assert "SERVER_OK" in r.stdout


def test_server_raises_without_mongo_url():
    """Required-var validation should raise with a clear message."""
    r = subprocess.run(
        [sys.executable, "-c", "import dotenv;dotenv.load_dotenv=lambda *a,**k:False;import os;os.environ.pop('MONGO_URL',None);os.environ.setdefault('JWT_SECRET','x');import server"],
        cwd="/app/backend",
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode != 0, "server should fail without MONGO_URL"
    assert "MONGO_URL is required" in (r.stdout + r.stderr), f"bad error: {r.stdout}{r.stderr}"


def test_server_raises_without_jwt_secret():
    r = subprocess.run(
        [sys.executable, "-c", "import dotenv;dotenv.load_dotenv=lambda *a,**k:False;import os;os.environ.pop('JWT_SECRET',None);os.environ.setdefault('MONGO_URL','mongodb://localhost:27017');import server"],
        cwd="/app/backend",
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode != 0, "server should fail without JWT_SECRET"
    assert "JWT_SECRET is required" in (r.stdout + r.stderr), f"bad error: {r.stdout}{r.stderr}"


def test_startup_banner_logs_configured_services():
    """check_env() should log a summary of what's configured."""
    r = _run_in_clean_env("import server; print('DONE')")
    assert r.returncode == 0
    combined = r.stdout + r.stderr
    assert "[startup] Required env OK" in combined
    assert "MONGO_URL" in combined
    assert "JWT_SECRET" in combined
