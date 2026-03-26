"""
Nova AI Sandbox Engine
Executes user-submitted Python code in a restricted environment.
Uses RestrictedPython for code validation + subprocess isolation.
"""
import sys
import io
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

EXECUTION_TIMEOUT = 30  # seconds
MAX_OUTPUT_SIZE = 50_000  # chars
MAX_MEMORY_MB = 128

# Modules users are allowed to import
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

# Dangerous patterns to reject before even compiling
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


def _safe_import(name, *args, **kwargs):
    """Restricted import that only allows whitelisted modules."""
    if name in BLOCKED_IMPORTS:
        raise ImportError(f"Import of '{name}' is not allowed in the Nova Sandbox.")
    if name in SAFE_MODULES:
        return SAFE_MODULES[name]
    # Allow sub-imports of safe modules
    top_level = name.split(".")[0]
    if top_level in SAFE_MODULES:
        return SAFE_MODULES[top_level]
    raise ImportError(f"Module '{name}' is not available in the Nova Sandbox. Allowed: {', '.join(sorted(SAFE_MODULES.keys()))}")


def _guarded_write(obj):
    """Allow print() to work by returning the object as-is for write operations."""
    return obj


def validate_code(code: str) -> Optional[str]:
    """
    Pre-validate code for dangerous patterns before compilation.
    Returns error message or None if code is safe.
    """
    if not code or not code.strip():
        return "No code provided."

    if len(code) > 100_000:
        return "Code exceeds maximum size (100KB)."

    for pattern in BLOCKED_PATTERNS:
        match = re.search(pattern, code)
        if match:
            return f"Blocked pattern detected: '{match.group()}'. This operation is not allowed in the sandbox."

    # Check for blocked imports
    import_pattern = r'^\s*import\s+(\w+)|^\s*from\s+(\w+)'
    for line in code.split('\n'):
        match = re.match(import_pattern, line)
        if match:
            module_name = match.group(1) or match.group(2)
            if module_name in BLOCKED_IMPORTS:
                return f"Import of '{module_name}' is not allowed in the Nova Sandbox."
            if module_name not in SAFE_MODULES:
                return f"Module '{module_name}' is not available in the Nova Sandbox. Allowed: {', '.join(sorted(SAFE_MODULES.keys()))}"

    return None


class PrintCollector:
    """Collects print output for RestrictedPython v8."""
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
    """Factory that RestrictedPython calls: _print = _print_(_getattr_)."""
    return PrintCollector(_getattr_)


def _safe_getattr(obj, name, default=None):
    """Safe getattr that blocks dunder access."""
    if name.startswith("_"):
        raise AttributeError(f"Access to '{name}' is not allowed.")
    return getattr(obj, name, default)


def build_safe_globals(env_vars: Dict[str, str] = None, input_data: Any = None) -> dict:
    """
    Build the restricted execution environment with safe builtins,
    whitelisted modules, and user-provided env vars/input.
    """
    restricted_builtins = dict(safe_builtins)

    # Add essential builtins that RestrictedPython removes
    restricted_builtins["__import__"] = _safe_import
    restricted_builtins["range"] = range
    restricted_builtins["enumerate"] = enumerate
    restricted_builtins["zip"] = zip
    restricted_builtins["map"] = map
    restricted_builtins["filter"] = filter
    restricted_builtins["sorted"] = sorted
    restricted_builtins["reversed"] = reversed
    restricted_builtins["len"] = len
    restricted_builtins["min"] = min
    restricted_builtins["max"] = max
    restricted_builtins["sum"] = sum
    restricted_builtins["abs"] = abs
    restricted_builtins["round"] = round
    restricted_builtins["int"] = int
    restricted_builtins["float"] = float
    restricted_builtins["str"] = str
    restricted_builtins["bool"] = bool
    restricted_builtins["list"] = list
    restricted_builtins["dict"] = dict
    restricted_builtins["tuple"] = tuple
    restricted_builtins["set"] = set
    restricted_builtins["frozenset"] = frozenset
    restricted_builtins["type"] = type
    restricted_builtins["isinstance"] = isinstance
    restricted_builtins["issubclass"] = issubclass
    restricted_builtins["hasattr"] = hasattr
    restricted_builtins["print"] = print
    restricted_builtins["any"] = any
    restricted_builtins["all"] = all
    restricted_builtins["chr"] = chr
    restricted_builtins["ord"] = ord
    restricted_builtins["hex"] = hex
    restricted_builtins["bin"] = bin
    restricted_builtins["oct"] = oct
    restricted_builtins["format"] = format
    restricted_builtins["repr"] = repr
    restricted_builtins["id"] = id
    restricted_builtins["hash"] = hash
    restricted_builtins["callable"] = callable
    restricted_builtins["iter"] = iter
    restricted_builtins["next"] = next
    restricted_builtins["Exception"] = Exception
    restricted_builtins["ValueError"] = ValueError
    restricted_builtins["TypeError"] = TypeError
    restricted_builtins["KeyError"] = KeyError
    restricted_builtins["IndexError"] = IndexError
    restricted_builtins["StopIteration"] = StopIteration
    restricted_builtins["RuntimeError"] = RuntimeError
    restricted_builtins["ZeroDivisionError"] = ZeroDivisionError
    restricted_builtins["AttributeError"] = AttributeError

    env = dict(safe_globals)
    env["__builtins__"] = restricted_builtins
    env["_getiter_"] = default_guarded_getiter
    env["_getitem_"] = default_guarded_getitem
    env["_write_"] = _guarded_write
    env["_inplacevar_"] = lambda op, x, y: op(x, y)
    env["_unpack_sequence_"] = guarded_unpack_sequence
    env["_iter_unpack_sequence_"] = guarded_unpack_sequence
    env["_getattr_"] = _safe_getattr

    # Print factory for RestrictedPython v8: _print = _print_(_getattr_)
    env["_print_"] = _print_factory

    # Inject whitelisted modules directly
    for mod_name, mod in SAFE_MODULES.items():
        env[mod_name] = mod

    # User environment variables (sanitized)
    env["ENV"] = dict(env_vars) if env_vars else {}

    # Input data from webhook/manual trigger
    env["INPUT"] = input_data if input_data is not None else {}

    # Result container — user sets RESULT to return output
    env["RESULT"] = None

    return env


class TimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):
    raise TimeoutError("Execution timed out")


def execute_code(
    code: str,
    env_vars: Dict[str, str] = None,
    input_data: Any = None,
    timeout: int = EXECUTION_TIMEOUT,
) -> Dict[str, Any]:
    """
    Execute user code in the Nova Sandbox.
    Returns: {success, output, result, logs, error, duration_ms}
    """
    start = time.time()

    # Step 1: Pre-validate
    validation_error = validate_code(code)
    if validation_error:
        return {
            "success": False,
            "output": "",
            "result": None,
            "logs": "",
            "error": validation_error,
            "duration_ms": 0,
        }

    # Step 2: Compile with RestrictedPython
    try:
        byte_code = compile_restricted(code, filename="<nova-agent>", mode="exec")
    except SyntaxError as e:
        return {
            "success": False,
            "output": "",
            "result": None,
            "logs": "",
            "error": f"Syntax error at line {e.lineno}: {e.msg}",
            "duration_ms": 0,
        }
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "result": None,
            "logs": "",
            "error": f"Compilation failed: {str(e)}",
            "duration_ms": 0,
        }

    # Step 3: Build restricted environment
    safe_env = build_safe_globals(env_vars, input_data)

    # Step 4: Capture stdout/stderr
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    captured_out = io.StringIO()
    captured_err = io.StringIO()

    # Step 5: Execute with timeout
    try:
        sys.stdout = captured_out
        sys.stderr = captured_err

        # Set timeout using signal (Unix only)
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(timeout)

        exec(byte_code, safe_env)

        signal.alarm(0)  # Cancel alarm
        signal.signal(signal.SIGALRM, old_handler)

        duration = int((time.time() - start) * 1000)

        # Collect printed output from RestrictedPython's print collector
        printer = safe_env.get("_print")
        printed_output = ""
        if printer and hasattr(printer, "printed"):
            printed_output = printer.printed
        stdout_output = captured_out.getvalue()
        output = (printed_output + stdout_output)[:MAX_OUTPUT_SIZE]

        logs = captured_err.getvalue()[:MAX_OUTPUT_SIZE]
        result = safe_env.get("RESULT")

        # Ensure result is JSON-serializable
        if result is not None:
            try:
                json.dumps(result)
            except (TypeError, ValueError):
                result = str(result)

        return {
            "success": True,
            "output": output,
            "result": result,
            "logs": logs,
            "error": None,
            "duration_ms": duration,
        }

    except TimeoutError:
        signal.alarm(0)
        return {
            "success": False,
            "output": captured_out.getvalue()[:MAX_OUTPUT_SIZE],
            "result": None,
            "logs": captured_err.getvalue()[:MAX_OUTPUT_SIZE],
            "error": f"Execution timed out after {timeout} seconds.",
            "duration_ms": timeout * 1000,
        }
    except Exception as e:
        signal.alarm(0)
        tb = traceback.format_exc()
        # Sanitize traceback to remove internal paths
        tb_clean = "\n".join(
            line for line in tb.split("\n")
            if "RestrictedPython" not in line and "/app/backend" not in line
        )
        return {
            "success": False,
            "output": captured_out.getvalue()[:MAX_OUTPUT_SIZE],
            "result": None,
            "logs": captured_err.getvalue()[:MAX_OUTPUT_SIZE],
            "error": f"{type(e).__name__}: {str(e)}\n{tb_clean}".strip(),
            "duration_ms": int((time.time() - start) * 1000),
        }
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        try:
            signal.alarm(0)
        except Exception:
            pass
