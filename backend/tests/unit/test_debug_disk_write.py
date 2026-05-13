"""Unit tests for debug disk write — FIX-CR-05."""
import pytest
import inspect


def test_traces_router_no_disk_write():
    """CRITICAL-05: traces.py should not write to .log files."""
    from app.routers import traces

    source = inspect.getsource(traces)

    # Check for file write patterns (excluding comments and docstrings)
    lines = source.split('\n')
    violations = []
    in_docstring = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        
        # Toggle docstring state
        if '"""' in line or "'''" in line:
            in_docstring = not in_docstring
            continue
        if in_docstring:
            continue
        # Skip comments
        if stripped.startswith('#'):
            continue
        # Skip lines containing "open()" in parentheses (e.g., docstrings describing blocked patterns)
        if 'open()' in line:
            continue
        # Check for file write patterns
        for pattern in [".write(", "debug-save.log", "write_debug_log"]:
            if pattern in line:
                violations.append(f"Line {i}: {stripped}")
                break

    assert len(violations) == 0, (
        f"CRITICAL-05: Found disk-write patterns in traces.py:\n"
        + "\n".join(violations)
        + "\nReplace write_debug_log with structured logging (logger.debug/info/warning)."
    )


def test_auth_router_no_disk_write():
    """CRITICAL-05: auth.py should not write to .log files."""
    from app.routers import auth

    source = inspect.getsource(auth)

    # Check for file write patterns (excluding legitimate json usage)
    lines = source.split('\n')
    violations = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Skip json.loads/json.dumps (legitimate Supabase API usage)
        if 'json.loads' in stripped or 'json.dumps' in stripped:
            continue
        # Check for disk write patterns
        if any(p in stripped for p in ["open(", ".write(", "debug-save.log", "write_debug_log"]):
            violations.append(f"Line {i}: {stripped}")

    assert len(violations) == 0, (
        f"CRITICAL-05: Found disk-write patterns in auth.py:\n"
        + "\n".join(violations)
        + "\nReplace write_debug_log with structured logging."
    )
