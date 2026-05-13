"""
Tracer runner — spawns a subprocess to run the tracer with resource limits.

Key design decisions:
  - Subprocess isolation: user code runs in its own process, cannot crash FastAPI.
  - 5-second timeout as primary guard on all platforms.
  - resource.setrlimit() as secondary CPU/memory guard on Linux (Railway).
  - Max 500 steps as loop protection.
  - Temp file written for code (no shell injection from inline code).
"""
from __future__ import annotations

import os
import sys
import json
import uuid
import subprocess
import tempfile
import logging
import shutil

try:
    import resource  # Unix-only; skipped on Windows
except ImportError:
    resource = None  # type: ignore[assignment]

from app.config import settings

logger = logging.getLogger("codescope.tracer_runner")

TRACER_LIB_PATH = settings.tracer_lib_path
MAX_STEPS = settings.tracer_max_steps
TIMEOUT_SECONDS = settings.tracer_timeout_seconds


def _get_python_executable() -> str:
    """Return the Python executable for the current process."""
    return sys.executable


def run_trace(code: str) -> dict:
    """
    Spawn a subprocess that runs the tracer on user code.
    
    Security: Code is written to a temp file (not passed as inline -c argument)
    to prevent shell injection from crafted code strings.
    
    Returns: TraceResult dict
    """
    trace_id = str(uuid.uuid4())
    temp_file = None
    
    try:
        # Write code to a temp file (prevents shell injection)
        fd, temp_file = tempfile.mkstemp(suffix=".py", prefix=f"codescope_{trace_id}_")
        with os.fdopen(fd, "w") as f:
            f.write(code)
        
        # Build the tracing script
        # The script imports the tracer library and runs it on the temp file
        script = f"""
import sys
import os
import json
import traceback

# Add tracer library to path
sys.path.insert(0, r'{TRACER_LIB_PATH.replace(chr(92), chr(92) + chr(92))}')

# Apply resource limits on Unix (Railway = Linux)
try:
    import importlib.util
    if importlib.util.find_spec("resource") is not None:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, ({TIMEOUT_SECONDS}, {TIMEOUT_SECONDS + 1}))
        SOFT, HARD = 256 * 1024 * 1024, 512 * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (SOFT, HARD))
        resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))
except Exception:
    # resource not available on Windows; silently skip
    pass

# Run the tracer
try:
    from tracer.tracer import run_trace as _run_trace
    
    with open(r'{temp_file.replace(chr(92), chr(92) + chr(92))}', 'r') as f:
        code_to_trace = f.read()
    
    result = _run_trace(
        code_to_trace,
        max_steps={MAX_STEPS},
        timeout_seconds={TIMEOUT_SECONDS},
    )
    print("__CODESCOPE_RESULT__" + json.dumps(result) + "__CODESCOPE_END__")
    
except SyntaxError as e:
    print("__CODESCOPE_RESULT__" + json.dumps({{
        "error": "SYNTAX_ERROR",
        "error_message": str(e),
        "line": e.lineno,
        "steps": [],
        "total_steps": 0,
        "duration_ms": 0,
    }}) + "__CODESCOPE_END__")
except Exception as e:
    print("__CODESCOPE_RESULT__" + json.dumps({{
        "error": "EXECUTION_ERROR",
        "error_message": traceback.format_exc(),
        "steps": [],
        "total_steps": 0,
        "duration_ms": 0,
    }}) + "__CODESCOPE_END__")
"""
        
        # Spawn subprocess
        python_exe = _get_python_executable()
        
        proc = subprocess.Popen(
            [python_exe, "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        
        try:
            stdout_bytes, stderr_bytes = proc.communicate(timeout=TIMEOUT_SECONDS + 1)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()  # Drain
            logger.warning("trace_timeout", extra={"trace_id": trace_id})
            return {
                "error": "TIMEOUT",
                "error_message": f"Execution exceeded {TIMEOUT_SECONDS} seconds",
                "trace_id": trace_id,
                "steps": [],
                "total_steps": 0,
                "duration_ms": TIMEOUT_SECONDS * 1000,
            }
        
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        
        # Parse result from output
        if "__CODESCOPE_RESULT__" in stdout:
            try:
                result_str = stdout.split("__CODESCOPE_RESULT__")[1].split("__CODESCOPE_END__")[0]
                result = json.loads(result_str)
                result["trace_id"] = trace_id
                return result
            except (json.JSONDecodeError, IndexError) as e:
                logger.error("trace_parse_error", extra={"trace_id": trace_id, "error": str(e), "stdout": stdout[:500]})
                return {
                    "error": "PARSE_ERROR",
                    "error_message": f"Failed to parse tracer output: {e}",
                    "trace_id": trace_id,
                    "steps": [],
                    "total_steps": 0,
                    "duration_ms": 0,
                }
        
        # No result found — check stderr
        if stderr:
            logger.error("trace_stderr", extra={"trace_id": trace_id, "stderr": stderr[:500]})
        
        if proc.returncode != 0:
            return {
                "error": "RUNTIME_ERROR",
                "error_message": stderr[:500] if stderr else "Process exited with non-zero status",
                "trace_id": trace_id,
                "steps": [],
                "total_steps": 0,
                "duration_ms": 0,
            }
        
        # Empty output
        return {
            "error": "EMPTY_OUTPUT",
            "error_message": "Tracer produced no output",
            "trace_id": trace_id,
            "steps": [],
            "total_steps": 0,
            "duration_ms": 0,
        }
        
    finally:
        # Clean up temp file
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass
