"""Unit tests for Python sandbox security and AST validation."""
from tracer.validator import validate_code

def test_sandbox_allows_standard_python():
    """Tracer should allow normal Python logic (math, conditions, functions)."""
    code = "def fib(n):\n    if n <= 1:\n        return n\n    return fib(n-1) + fib(n-2)\nx = fib(5)"
    is_valid, blocking, warnings = validate_code(code)
    assert is_valid
    assert len(blocking) == 0

def test_sandbox_blocks_direct_import():
    """Tracer should block standard forbidden library imports."""
    code = "import os\nprint(os.getcwd())"
    is_valid, blocking, warnings = validate_code(code)
    assert not is_valid
    assert len(blocking) > 0

def test_sandbox_blocks_importlib_bypass():
    """Tracer should block indirect dynamic imports via importlib."""
    code = "import importlib\nos = importlib.import_module('os')"
    is_valid, blocking, warnings = validate_code(code)
    assert not is_valid

def test_sandbox_blocks_dunder_escapes():
    """Tracer should block attribute escape lookups like __subclasses__."""
    code = "x = ().__class__.__base__.__subclasses__()"
    is_valid, blocking, warnings = validate_code(code)
    assert not is_valid

def test_sandbox_blocks_eval_exec():
    """Tracer should block calling eval() and exec()."""
    for func in ("eval", "exec", "open", "getattr", "setattr"):
        code = f"x = {func}('some_argument')"
        is_valid, blocking, warnings = validate_code(code)
        assert not is_valid, f"Should have blocked {func}()"

def test_sandbox_blocks_builtins_access():
    """Tracer should block references to the __builtins__ namespace."""
    code = "x = __builtins__\nx['eval']('1 + 1')"
    is_valid, blocking, warnings = validate_code(code)
    assert not is_valid
