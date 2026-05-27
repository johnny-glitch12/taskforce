"""
Task Force AI — Hardened Workflow Sandbox

Executes workflow nodes in isolated, ephemeral Python environments.
Each execution gets its own globals dict that is destroyed after return.

Security layers:
  1. RestrictedPython compilation (AST-level blocking)
  2. Import whitelist (no os, sys, subprocess, pathlib, etc.)
  3. Pattern blocklist (no __import__, eval, exec, open, dunders)
  4. SSRF protection on all HTTP calls (blocks private IPs, metadata endpoints)
  5. 30-second hard timeout via SIGALRM
  6. 128MB memory cap conceptual (enforced by container limits)
  7. Output capped at 50KB
  8. BYOK credentials injected as ephemeral locals, wiped after execution
"""
import sys
import io
import gc
import time
import signal
import traceback
import json
import math
import re
import random
import string
import hashlib
import base64
import datetime
import collections
from typing import Dict, Any, Optional
from RestrictedPython import compile_restricted, safe_globals
from RestrictedPython.Guards import safe_builtins, guarded_unpack_sequence
from RestrictedPython.Eval import default_guarded_getiter, default_guarded_getitem

EXECUTION_TIMEOUT = 30
MAX_OUTPUT_SIZE = 50_000
MAX_MEMORY_MB = 128

# ── Safe modules (extended for workflow execution) ──
SAFE_MODULES = {
    "json": json,
    "math": math,
    "re": re,
    "random": random,
    "string": string,
    "hashlib": hashlib,
    "base64": base64,
    "datetime": datetime,
    "collections": collections,
}

# ── Blocked patterns ──
BLOCKED_PATTERNS = [
    r"__import__\s*\(",
    r"eval\s*\(",
    r"exec\s*\(",
    r"compile\s*\(",
    r"globals\s*\(",
    r"locals\s*\(",
    r"getattr\s*\(",
    r"setattr\s*\(",
    r"delattr\s*\(",
    r"open\s*\(",
    r"__builtins__",
    r"__subclasses__",
    r"__bases__",
    r"__class__",
    r"__mro__",
]

BLOCKED_IMPORTS = {
    "os", "sys", "subprocess", "socket", "shutil", "importlib",
    "ctypes", "multiprocessing", "threading", "signal", "resource",
    "pty", "fcntl", "termios", "code", "codeop", "compileall",
    "pickle", "shelve", "marshal", "builtins", "io", "pathlib",
    "tempfile", "glob", "fnmatch", "http", "urllib", "ftplib",
    "smtplib", "poplib", "imaplib", "telnetlib", "xmlrpc",
    "webbrowser", "cmd", "pdb", "profile", "pstats",
}


# ── SSRF-safe HTTP function for sandbox use ──
def _make_safe_http(user_api_keys: dict):
    """Creates a sandboxed HTTP function that prevents SSRF and injects BYOK headers."""
    from lib.executor_security import validate_url
    import httpx

    def safe_request(url: str, method: str = "GET", headers: dict = None, body=None, timeout: int = 15):
        """SSRF-safe HTTP request. Blocks private IPs, metadata endpoints, dangerous ports."""
        validation = validate_url(url)
        if not validation["safe"]:
            return {"ok": False, "status": 0, "error": validation["reason"], "body": ""}

        req_headers = dict(headers or {})
        # Inject BYOK keys if header references them
        for k, v in req_headers.items():
            if isinstance(v, str) and v.startswith("{{") and v.endswith("}}"):
                key_name = v[2:-2].strip()
                if key_name in user_api_keys:
                    req_headers[k] = user_api_keys[key_name]

        try:
            with httpx.Client(timeout=min(timeout, 15), follow_redirects=False, verify=True) as client:
                response = client.request(method, url, headers=req_headers, content=json.dumps(body) if body and isinstance(body, dict) else body)
                return {
                    "ok": response.status_code < 400,
                    "status": response.status_code,
                    "body": response.text[:10000],
                    "error": None,
                }
        except Exception as e:
            return {"ok": False, "status": 0, "body": "", "error": str(e)[:200]}

    return safe_request


def _safe_import(name, *args, **kwargs):
    """Restricted import allowing only whitelisted modules."""
    if name in BLOCKED_IMPORTS:
        raise ImportError(f"Import of '{name}' is blocked. Security violation.")
    if name in SAFE_MODULES:
        return SAFE_MODULES[name]
    top_level = name.split(".")[0]
    if top_level in SAFE_MODULES:
        return SAFE_MODULES[top_level]
    raise ImportError(f"Module '{name}' is not available. Allowed: {', '.join(sorted(SAFE_MODULES.keys()))}")


def _guarded_write(obj):
    return obj


def _safe_getattr(obj, name, default=None):
    if name.startswith("_"):
        raise AttributeError(f"Access to '{name}' is blocked.")
    return getattr(obj, name, default)


class PrintCollector:
    def __init__(self, _getattr_=None):
        self._lines = []

    def _call_print(self, *args, **kwargs):
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        self._lines.append(sep.join(str(a) for a in args) + end)

    @property
    def printed(self):
        return "".join(self._lines)


def _print_factory(_getattr_=None):
    return PrintCollector(_getattr_)


def validate_code(code: str) -> Optional[str]:
    """Pre-validate code for dangerous patterns. Returns error or None."""
    if not code or not code.strip():
        return "No code provided."
    if len(code) > 100_000:
        return "Code exceeds 100KB limit."
    for pattern in BLOCKED_PATTERNS:
        match = re.search(pattern, code)
        if match:
            return f"Blocked pattern: '{match.group()}'"
    import_pattern = r'^\s*import\s+(\w+)|^\s*from\s+(\w+)'
    for line in code.split('\n'):
        match = re.match(import_pattern, line)
        if match:
            mod = match.group(1) or match.group(2)
            if mod in BLOCKED_IMPORTS:
                return f"Import of '{mod}' is blocked."
            if mod not in SAFE_MODULES:
                return f"Module '{mod}' not available. Allowed: {', '.join(sorted(SAFE_MODULES.keys()))}"
    return None


class ExecutionTimeout(Exception):
    pass


def _timeout_handler(signum, frame):
    raise ExecutionTimeout("Execution timed out")


def execute_sandboxed(
    code: str,
    user_api_keys: Dict[str, str] = None,
    input_data: Any = None,
    env_vars: Dict[str, str] = None,
    timeout: int = EXECUTION_TIMEOUT,
) -> Dict[str, Any]:
    """
    Execute code in the hardened sandbox.

    Args:
        code: Python code string
        user_api_keys: BYOK credentials (injected as KEYS dict, wiped after execution)
        input_data: Input payload from trigger/previous node
        env_vars: Agent environment variables
        timeout: Max seconds

    Returns: {success, output, result, logs, error, duration_ms}
    """
    start = time.time()
    safe_env = None

    # Step 1: Validate
    err = validate_code(code)
    if err:
        return {"success": False, "output": "", "result": None, "logs": "", "error": err, "duration_ms": 0}

    # Step 2: Compile
    try:
        byte_code = compile_restricted(code, filename="<taskforce-sandbox>", mode="exec")
    except SyntaxError as e:
        return {"success": False, "output": "", "result": None, "logs": "", "error": f"Syntax error line {e.lineno}: {e.msg}", "duration_ms": 0}
    except Exception as e:
        return {"success": False, "output": "", "result": None, "logs": "", "error": f"Compile failed: {e}", "duration_ms": 0}

    # Step 3: Build environment
    restricted_builtins = dict(safe_builtins)
    for name, obj in [
        ("__import__", _safe_import), ("range", range), ("enumerate", enumerate),
        ("zip", zip), ("map", map), ("filter", filter), ("sorted", sorted),
        ("reversed", reversed), ("len", len), ("min", min), ("max", max),
        ("sum", sum), ("abs", abs), ("round", round), ("int", int), ("float", float),
        ("str", str), ("bool", bool), ("list", list), ("dict", dict), ("tuple", tuple),
        ("set", set), ("frozenset", frozenset), ("type", type), ("isinstance", isinstance),
        ("issubclass", issubclass), ("hasattr", hasattr), ("print", print),
        ("any", any), ("all", all), ("chr", chr), ("ord", ord), ("hex", hex),
        ("bin", bin), ("oct", oct), ("format", format), ("repr", repr),
        ("id", id), ("hash", hash), ("callable", callable), ("iter", iter), ("next", next),
        ("Exception", Exception), ("ValueError", ValueError), ("TypeError", TypeError),
        ("KeyError", KeyError), ("IndexError", IndexError), ("StopIteration", StopIteration),
        ("RuntimeError", RuntimeError), ("ZeroDivisionError", ZeroDivisionError),
        ("AttributeError", AttributeError),
    ]:
        restricted_builtins[name] = obj

    safe_env = dict(safe_globals)
    safe_env["__builtins__"] = restricted_builtins
    safe_env["_getiter_"] = default_guarded_getiter
    safe_env["_getitem_"] = default_guarded_getitem
    safe_env["_write_"] = _guarded_write
    safe_env["_inplacevar_"] = lambda op, x, y: op(x, y)
    safe_env["_unpack_sequence_"] = guarded_unpack_sequence
    safe_env["_iter_unpack_sequence_"] = guarded_unpack_sequence
    safe_env["_getattr_"] = _safe_getattr
    safe_env["_print_"] = _print_factory

    # Inject safe modules
    for mod_name, mod in SAFE_MODULES.items():
        safe_env[mod_name] = mod

    # Inject SSRF-safe HTTP function
    keys = dict(user_api_keys) if user_api_keys else {}
    safe_env["http_request"] = _make_safe_http(keys)

    # Inject user data
    safe_env["KEYS"] = keys  # BYOK credentials (ephemeral)
    safe_env["ENV"] = dict(env_vars) if env_vars else {}
    safe_env["INPUT"] = input_data if input_data is not None else {}
    safe_env["RESULT"] = None

    # Step 4: Execute with timeout
    old_stdout, old_stderr = sys.stdout, sys.stderr
    captured_out, captured_err = io.StringIO(), io.StringIO()

    try:
        sys.stdout = captured_out
        sys.stderr = captured_err
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(timeout)

        exec(byte_code, safe_env)

        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
        duration = int((time.time() - start) * 1000)

        printer = safe_env.get("_print")
        printed = printer.printed if printer and hasattr(printer, "printed") else ""
        output = (printed + captured_out.getvalue())[:MAX_OUTPUT_SIZE]
        result = safe_env.get("RESULT")

        if result is not None:
            try:
                json.dumps(result)
            except (TypeError, ValueError):
                result = str(result)

        return {"success": True, "output": output, "result": result, "logs": captured_err.getvalue()[:MAX_OUTPUT_SIZE], "error": None, "duration_ms": duration}

    except ExecutionTimeout:
        signal.alarm(0)
        return {"success": False, "output": captured_out.getvalue()[:MAX_OUTPUT_SIZE], "result": None, "logs": "", "error": f"Timeout after {timeout}s", "duration_ms": timeout * 1000}
    except Exception as e:
        signal.alarm(0)
        tb = traceback.format_exc()
        tb_clean = "\n".join(l for l in tb.split("\n") if "RestrictedPython" not in l and "/app/" not in l)
        return {"success": False, "output": captured_out.getvalue()[:MAX_OUTPUT_SIZE], "result": None, "logs": "", "error": f"{type(e).__name__}: {e}\n{tb_clean}".strip(), "duration_ms": int((time.time() - start) * 1000)}
    finally:
        # ── EPHEMERAL WIPE: Destroy all sensitive data from memory ──
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        try:
            signal.alarm(0)
        except Exception:
            pass
        if safe_env:
            safe_env.get("KEYS", {}).clear()
            safe_env.get("ENV", {}).clear()
            safe_env.clear()
        keys.clear()
        del safe_env, keys, byte_code
        gc.collect()
