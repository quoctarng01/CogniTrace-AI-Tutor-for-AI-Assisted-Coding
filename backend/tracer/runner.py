"""
Subprocess runner for executing untrusted user code.
Handles: temp file cleanup, 5s timeout, stderr capture, Windows compat.
"""
import os
import sys
import json
import tempfile
import subprocess
import io
from pathlib import Path
from tracer.models import SandboxError


def run_trace(source: str, max_steps: int = 500, timeout_seconds: int = 5) -> dict:
    """
    Execute user code in an isolated subprocess.
    Returns: {"steps": [...], "total_steps": int, "duration_ms": float}
    Errors: {"error": str, "message": str, "line": int?}
    """
    fd, tmp_path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            # Add backend/ to path so 'tracer' is importable as a package
            backend_dir = str(Path(__file__).parent.parent)
            escaped_dir = backend_dir.replace("\\", "\\\\")
            f.write(f"import sys, json, io, time\n")
            f.write(f"sys.path.insert(0, r'{escaped_dir}')\n")
            # Capture stdout so print() doesn't pollute JSON output
            f.write(f"sys.stdout = io.StringIO()\n")
            f.write(f"from tracer import tracer as _tracer\n")
            f.write(f"from tracer.models import SandboxError\n")
            f.write(f"try:\n")
            f.write(f"    result = _tracer.run_trace({repr(source)}, max_steps={max_steps})\n")
            f.write(f"except SandboxError as e:\n")
            f.write(f"    result = {{'error': 'SANDBOX_ERROR', 'message': str(e), 'pattern': e.pattern}}\n")
            f.write(f"sys.stdout = sys.__stdout__\n")
            f.write(f"print(json.dumps(result))\n")

        # Run the temp file in a subprocess
        proc = subprocess.Popen(
            [sys.executable, tmp_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            stdout, stderr = proc.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            # Windows: proc.kill() works fine on Windows Python 3.7+
            proc.kill()
            proc.communicate()  # drain pipes to avoid BrokenPipeError
            return {
                "error": "TIMEOUT",
                "message": f"Execution exceeded {timeout_seconds} seconds",
                "line": None,
            }

        # Decode output (handle encoding edge cases)
        try:
            stdout_text = stdout.decode("utf-8", errors="replace").strip()
        except Exception:
            stdout_text = ""

        try:
            stderr_text = stderr.decode("utf-8", errors="replace").strip()
        except Exception:
            stderr_text = ""

        # Empty stdout means the subprocess crashed
        if not stdout_text:
            return {
                "error": "EXECUTION_ERROR",
                "message": stderr_text or "Code produced no output. Check for crashes.",
                "line": None,
            }

        # Parse the JSON result from the subprocess
        try:
            return json.loads(stdout_text)
        except json.JSONDecodeError as e:
            return {
                "error": "EXECUTION_ERROR",
                "message": f"JSON parse error: {e}\nOutput: {stdout_text[:500]}",
                "line": None,
            }

    finally:
        # ALWAYS delete the temp file, even if an exception occurs
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
