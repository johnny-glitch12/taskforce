"""
Agent Runner Harness — copied into every external agent's directory at install time.

Reads a JSON payload from stdin (with keys: entry_path, entry_fn, input, env, keys),
imports the entry module from disk, calls entry_function with the right signature,
runs sync OR async results, and emits a single sentinel-tagged line on stdout:

    ___TFAI_RESULT___{"ok": bool, "result": any} OR {"ok": false, "error": str, "trace": str}

The harness is intentionally minimal and dependency-free so it works with any
agent's venv regardless of installed packages.
"""
import sys
import os
import json
import inspect
import importlib.util
import asyncio
import traceback

SENTINEL = "___TFAI_RESULT___"


def _load_callable(entry_path: str, entry_fn: str):
    if not os.path.isfile(entry_path):
        raise RuntimeError(f"entry_point file not found: {entry_path}")
    # Insert the agent's code directory onto sys.path so sibling files import cleanly.
    code_dir = os.path.dirname(os.path.abspath(entry_path))
    if code_dir not in sys.path:
        sys.path.insert(0, code_dir)
    spec = importlib.util.spec_from_file_location("agent_entry", entry_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load entry module from {entry_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    fn = getattr(mod, entry_fn, None)
    if fn is None:
        raise RuntimeError(f"entry_function `{entry_fn}` not defined in {os.path.basename(entry_path)}")
    if not callable(fn):
        raise RuntimeError(f"`{entry_fn}` is not callable")
    return fn


def _invoke(fn, input_data, env_vars, keys):
    """Call `fn` with whatever subset of (input, env, keys) it actually accepts."""
    sig = inspect.signature(fn)
    params = sig.parameters
    if len(params) == 0:
        return fn()
    # Pass input as the first positional arg; env/keys as kwargs IF accepted.
    kwargs = {}
    if "env" in params:
        kwargs["env"] = env_vars
    if "keys" in params:
        kwargs["keys"] = keys
    return fn(input_data, **kwargs)


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw or "{}")
    except Exception as e:
        sys.stdout.write(SENTINEL + json.dumps({"ok": False, "error": f"bad stdin payload: {e}"}))
        sys.stdout.flush()
        return 0

    entry_path = payload.get("entry_path") or ""
    entry_fn = payload.get("entry_fn") or ""
    input_data = payload.get("input") if payload.get("input") is not None else {}
    env_vars = payload.get("env") or {}
    keys = payload.get("keys") or {}

    # Make env vars visible to the agent via os.environ (read-only contract).
    for k, v in env_vars.items():
        if isinstance(k, str):
            os.environ[k] = str(v) if v is not None else ""

    try:
        fn = _load_callable(entry_path, entry_fn)
        result = _invoke(fn, input_data, env_vars, keys)
        if asyncio.iscoroutine(result):
            result = asyncio.run(result)
        try:
            # Ensure the result is JSON-serializable; fall back to repr on failure.
            json.dumps(result)
            json_result = result
        except (TypeError, ValueError):
            json_result = repr(result)
        sys.stdout.write("\n" + SENTINEL + json.dumps({"ok": True, "result": json_result}, default=str))
    except SystemExit as e:
        sys.stdout.write("\n" + SENTINEL + json.dumps({"ok": False, "error": f"SystemExit: {e.code}"}))
    except Exception as e:
        tb = traceback.format_exc()[-4000:]
        sys.stdout.write("\n" + SENTINEL + json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}", "trace": tb}))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
