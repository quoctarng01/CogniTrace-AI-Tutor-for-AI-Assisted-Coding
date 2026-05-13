"""Tests for the side-effect validator."""
import pytest
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
