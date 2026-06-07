"""Tests for the side-effect validator."""
from tracer.validator import validate_code


def test_safe_code_returns_valid():
    """Code with no side effects should be valid."""
    is_valid, blocking, warnings = validate_code("x = 1\ny = x + 2")
    assert is_valid is True
    assert len(blocking) == 0


def test_import_os_is_blocked():
    """import os should be blocked."""
    is_valid, blocking, warnings = validate_code("import os")
    assert is_valid is False
    assert any(e["pattern"] == "dangerous_import" for e in blocking)


def test_open_builtin_is_blocked():
    """open() should be blocked."""
    is_valid, blocking, warnings = validate_code("f = open('test.txt')")
    assert is_valid is False
    assert any(e["pattern"] == "file_io" for e in blocking)


def test_print_is_warning_not_block():
    """print() should be a warning only, not blocking."""
    is_valid, blocking, warnings = validate_code("print('hello')")
    assert is_valid is True
    assert len(blocking) == 0
    assert any(w["pattern"] == "print_statement" for w in warnings)


def test_multiple_blocking_effects():
    """Multiple dangerous patterns should all be reported."""
    code = "import os\nimport sys\nopen('x')"
    is_valid, blocking, warnings = validate_code(code)
    assert is_valid is False
    assert len(blocking) >= 2


def test_regex_does_not_false_positive():
    """Variable names starting with 'os' should not trigger os module block."""
    is_valid, blocking, warnings = validate_code("oscar = 'Oscar'")
    assert is_valid is True
    assert not any(e["pattern"] == "os_module" for e in blocking)


# ---------------------------------------------------------------------------
# Tests for expanded blocklist (added in Phase 1, Task 1.5)
# ---------------------------------------------------------------------------

def test_ctypes_blocked():
    """import ctypes must be blocked."""
    from tracer.validator import validate_code
    ok, blocking, _ = validate_code("import ctypes")
    assert not ok
    assert any(b["pattern"] == "dangerous_import" for b in blocking)


def test_threading_blocked():
    """import threading must be blocked."""
    from tracer.validator import validate_code
    ok, blocking, _ = validate_code("import threading")
    assert not ok


def test_multiprocessing_blocked():
    """import multiprocessing must be blocked."""
    from tracer.validator import validate_code
    ok, blocking, _ = validate_code("import multiprocessing")
    assert not ok


def test_gc_blocked():
    """import gc must be blocked (gc.get_referrers exposes internals)."""
    from tracer.validator import validate_code
    ok, blocking, _ = validate_code("import gc")
    assert not ok


def test_breakpoint_blocked():
    """breakpoint() call must be blocked."""
    from tracer.validator import validate_code
    ok, blocking, _ = validate_code("breakpoint()")
    assert not ok
    assert any(b["pattern"] == "dangerous_builtin" for b in blocking)


def test_globals_blocked():
    """globals() call must be blocked."""
    from tracer.validator import validate_code
    ok, blocking, _ = validate_code("x = globals()")
    assert not ok


def test_locals_blocked():
    """locals() call must be blocked."""
    from tracer.validator import validate_code
    ok, blocking, _ = validate_code("x = locals()")
    assert not ok


def test_vars_blocked():
    """vars() call must be blocked."""
    from tracer.validator import validate_code
    ok, blocking, _ = validate_code("x = vars()")
    assert not ok


def test_print_still_only_warning():
    """print() must still be a WARNING, not a block (regression test)."""
    from tracer.validator import validate_code
    ok, blocking, warnings = validate_code("print('hello')")
    assert ok, "print() should not be blocked"
    assert len(blocking) == 0
    assert any(w["pattern"] == "print_statement" for w in warnings)


def test_safe_code_still_passes_all_new_checks():
    """Regression: clean code passes all checks including new blocklist entries."""
    from tracer.validator import validate_code
    code = """
def fibonacci(n):
    a, b = 0, 1
    for i in range(n):
        a, b = b, a + b
    return a

result = fibonacci(8)
"""
    ok, blocking, _ = validate_code(code)
    assert ok
    assert len(blocking) == 0
