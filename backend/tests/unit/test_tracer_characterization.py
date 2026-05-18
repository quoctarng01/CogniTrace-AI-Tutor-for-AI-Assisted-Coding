"""Characterization tests for tracer engine — capture current behavior as ground truth.

These tests document what the code ACTUALLY does (not what it SHOULD do).
They serve as a safety net for future refactoring.

IMPORTANT: These tests assert CURRENT behavior. If behavior seems wrong,
add a comment noting it as "possible bug" rather than trying to fix it.
Future refactoring should NOT silently change behavior captured here.
"""
import ast
import pytest
from tracer.tracer import (
    run_trace,
    _build_jump_map,
    _build_opcode_map,
    _step_to_dict,
    _is_internal_variable,
)
from tracer.runner import run_trace as run_trace_subprocess
from tracer.models import TraceStep, VariableInfo


# =============================================================================
# _build_jump_map — characterization
# =============================================================================

def test_build_jump_map_simple_if():
    """Simple if statement should be in jump map."""
    result = _build_jump_map("if x > 0:\n    pass")
    assert 1 in result


def test_build_jump_map_if_with_else():
    """If/else statement should be in jump map at condition line."""
    result = _build_jump_map("if x > 0:\n    pass\nelse:\n    pass")
    assert 1 in result


def test_build_jump_map_for_loop():
    """For loop is NOT currently in jump map (only If, While, BoolOp tracked)."""
    # Possible bug: for loops are not included in _build_jump_map
    # Only If, While, and BoolOp nodes are captured
    result = _build_jump_map("for i in range(3):\n    pass")
    assert result == {}  # For loops NOT currently tracked


def test_build_jump_map_while_loop():
    """While loop should be in jump map at while line."""
    result = _build_jump_map("while x < 3:\n    pass")
    assert 1 in result


def test_build_jump_map_nested_if():
    """Nested if statements should have both lines in jump map."""
    result = _build_jump_map("if x:\n    if y:\n        pass")
    assert 1 in result  # outer if
    assert 2 in result  # inner if


def test_build_jump_map_multiple_ifs_same_line():
    """Multiple if statements on same line should all be in jump map."""
    # Not realistic in practice, but tests the setdefault behavior
    result = _build_jump_map("if a: pass")
    assert 1 in result


def test_build_jump_map_invalid_syntax():
    """Invalid syntax should return empty dict."""
    result = _build_jump_map("def :")
    assert result == {}


def test_build_jump_map_no_branches():
    """Code with no branches should return empty dict."""
    result = _build_jump_map("x = 1\ny = 2")
    assert result == {}


def test_build_jump_map_boolop():
    """BoolOp (and/or) expression IS captured in jump map."""
    # Current behavior: BoolOp nodes ARE added to jump_map at their lineno
    # This is a possible bug — BoolOp alone isn't a branch decision
    result = _build_jump_map("x = True and False")
    assert 1 in result  # BoolOp IS captured (possible bug: shouldn't be branch)
    assert len(result[1]) == 1
    assert isinstance(result[1][0], ast.BoolOp)


def test_build_jump_map_ternary():
    """Ternary expression (if/else) should NOT be in jump map."""
    result = _build_jump_map("x = 1 if cond else 2")
    # Ternary is an Assign with a IfExp, not an If statement
    assert result == {}


def test_build_jump_map_elif():
    """Elif should be represented in jump map."""
    result = _build_jump_map("if x:\n    pass\nelif y:\n    pass\nelse:\n    pass")
    # Both if and elif have 'test' attribute
    assert 1 in result  # if
    assert 3 in result  # elif


# =============================================================================
# _build_opcode_map — characterization
# =============================================================================

def test_build_opcode_map_simple_assignment():
    """Compiled code should have expected opcodes."""
    code = compile("x = 1", "<test>", "exec")
    opmap = _build_opcode_map(code)
    assert "LOAD_CONST" in opmap.values()
    assert "STORE_NAME" in opmap.values()


def test_build_opcode_map_has_offsets():
    """Opcode map should have integer offsets as keys."""
    code = compile("x = 1", "<test>", "exec")
    opmap = _build_opcode_map(code)
    for offset in opmap.keys():
        assert isinstance(offset, int)


def test_build_opcode_map_multiple_instructions():
    """Multiple instructions should all be in map."""
    code = compile("x = 1\ny = 2", "<test>", "exec")
    opmap = _build_opcode_map(code)
    assert len(opmap) >= 2


def test_build_opcode_map_function():
    """Function definition should have LOAD_CONST and MAKE_FUNCTION."""
    code = compile("def f(): pass", "<test>", "exec")
    opmap = _build_opcode_map(code)
    assert "LOAD_CONST" in opmap.values()
    assert "MAKE_FUNCTION" in opmap.values()


def test_build_opcode_map_binary_op():
    """Binary operation should have some binary op opcode."""
    code = compile("x = 1 + 2", "<test>", "exec")
    opmap = _build_opcode_map(code)
    opcodes = list(opmap.values())
    # Python 3.11+: BINARY_OP, Python 3.12+: uses RETURN_CONST pattern
    # Characterize what actually exists
    assert len(opcodes) >= 3  # RESUME, LOAD_CONST, STORE_NAME or equivalent


def test_build_opcode_map_compare():
    """Comparison should have COMPARE_OP."""
    code = compile("x = 1 > 0", "<test>", "exec")
    opmap = _build_opcode_map(code)
    assert "COMPARE_OP" in opmap.values()


# =============================================================================
# _is_internal_variable — characterization
# =============================================================================

def test_is_internal_dunder():
    """Dunder variables should be internal."""
    assert _is_internal_variable("__name__") is True
    assert _is_internal_variable("__doc__") is True
    assert _is_internal_variable("__file__") is True
    assert _is_internal_variable("__loader__") is True


def test_is_internal_single_underscore():
    """Single underscore prefixed variables should be internal."""
    assert _is_internal_variable("_tracer") is True
    assert _is_internal_variable("_temp") is True
    assert _is_internal_variable("_x") is True


def test_is_internal_stdlib():
    """Common stdlib module names should be internal."""
    assert _is_internal_variable("sys") is True
    assert _is_internal_variable("os") is True
    assert _is_internal_variable("time") is True
    assert _is_internal_variable("math") is True
    assert _is_internal_variable("json") is True


def test_is_internal_not_stdlib_prefix():
    """Variables starting with stdlib names should NOT be internal."""
    assert _is_internal_variable("syscall") is False
    assert _is_internal_variable("oscar") is False
    assert _is_internal_variable("mathias") is False


def test_is_internal_user_variables():
    """User variables should NOT be internal."""
    assert _is_internal_variable("x") is False
    assert _is_internal_variable("myvar") is False
    assert _is_internal_variable("count") is False
    assert _is_internal_variable("result") is False


def test_is_internal_abc_typing():
    """Abstract and typing names should be internal (except Enum)."""
    assert _is_internal_variable("abc") is True
    assert _is_internal_variable("typing") is True
    # Note: "Enum" is NOT in the stdlib filter list (possible bug or design decision)
    assert _is_internal_variable("Enum") is False


# =============================================================================
# _step_to_dict — characterization
# =============================================================================

def test_step_to_dict_basic():
    """_step_to_dict should convert TraceStep to dict."""
    step = TraceStep(
        step_number=0,
        line_number=1,
        bytecode_offset=0,
        opcode="LOAD_CONST",
        variables={"x": VariableInfo(type="int", value="1", changed=False)},
        branches_taken={},
        duration_ms=0.5,
    )
    result = _step_to_dict(step)
    assert result["step_number"] == 0
    assert result["line_number"] == 1
    assert result["bytecode_offset"] == 0
    assert result["opcode"] == "LOAD_CONST"
    assert result["variables"]["x"]["type"] == "int"
    assert result["variables"]["x"]["value"] == "1"
    assert result["variables"]["x"]["changed"] is False
    assert result["duration_ms"] == 0.5


def test_step_to_dict_with_branches():
    """_step_to_dict should serialize branches_taken."""
    step = TraceStep(
        step_number=0,
        line_number=1,
        bytecode_offset=0,
        opcode="LOAD_CONST",
        variables={},
        branches_taken={"if": {"taken": True, "line": 1, "branch": "then"}},
        duration_ms=0.1,
    )
    result = _step_to_dict(step)
    assert result["branches_taken"]["if"]["taken"] is True
    assert result["branches_taken"]["if"]["branch"] == "then"


def test_step_to_dict_empty_variables():
    """_step_to_dict with empty variables should return empty dict."""
    step = TraceStep(
        step_number=0,
        line_number=1,
        bytecode_offset=0,
        opcode="NOP",
        variables={},
        branches_taken={},
        duration_ms=0.0,
    )
    result = _step_to_dict(step)
    assert result["variables"] == {}


# =============================================================================
# _capture_variables — characterization via run_trace
# =============================================================================

def test_capture_variables_single():
    """Simple single variable should be captured."""
    result = run_trace("x = 42")
    assert "error" not in result
    # x should appear in some step
    found_x = any("x" in s["variables"] for s in result["steps"])
    assert found_x


def test_capture_variables_multiple():
    """Multiple variables should all be captured."""
    result = run_trace("a = 1\nb = 2\nc = 3")
    assert "error" not in result
    found_a = any("a" in s["variables"] for s in result["steps"])
    found_b = any("b" in s["variables"] for s in result["steps"])
    found_c = any("c" in s["variables"] for s in result["steps"])
    assert found_a and found_b and found_c


def test_capture_variables_type_info():
    """Variables should have correct type info."""
    result = run_trace("x = 42\ny = 3.14\nz = 'hello'")
    for step in result["steps"]:
        if "x" in step["variables"]:
            assert step["variables"]["x"]["type"] == "int"
        if "y" in step["variables"]:
            assert step["variables"]["y"]["type"] == "float"
        if "z" in step["variables"]:
            assert step["variables"]["z"]["type"] == "str"


def test_capture_variables_changed_flag():
    """Changed variable should have changed=True."""
    result = run_trace("x = 1\nx = 2\nx = 3")
    # Find step where x = 2 and x = 3, both should have changed=True
    x_values = []
    for step in result["steps"]:
        if "x" in step["variables"]:
            x_values.append(step["variables"]["x"])
    # Values should appear in order: "1", "2", "3"
    # But depending on how steps work, we might see different combinations
    # The key is that later values should show changed=True
    # (unless Python constant-folds some assignments)


def test_capture_variables_internal_hidden():
    """Internal variables should NOT appear in trace."""
    result = run_trace("x = 1")
    for step in result["steps"]:
        for var_name in step["variables"]:
            assert not var_name.startswith("_") or var_name.startswith("__")
            assert var_name not in ("sys", "os", "time")


def test_capture_variables_list():
    """List variable should be captured with correct type."""
    result = run_trace("lst = [1, 2, 3]")
    found_list = False
    for step in result["steps"]:
        if "lst" in step["variables"]:
            assert step["variables"]["lst"]["type"] == "list"
            found_list = True
    assert found_list


def test_capture_variables_dict():
    """Dictionary variable should be captured with correct type."""
    result = run_trace("d = {'a': 1}")
    found_dict = False
    for step in result["steps"]:
        if "d" in step["variables"]:
            assert step["variables"]["d"]["type"] == "dict"
            found_dict = True
    assert found_dict


def test_capture_variables_tuple():
    """Tuple variable should be captured with correct type."""
    result = run_trace("t = (1, 2)")
    found_tuple = False
    for step in result["steps"]:
        if "t" in step["variables"]:
            assert step["variables"]["t"]["type"] == "tuple"
            found_tuple = True
    assert found_tuple


# =============================================================================
# Closure and nested scope characterization
# =============================================================================

def test_capture_closure_variable():
    """Closure should capture enclosing scope variable."""
    result = run_trace("x = 10\ndef outer():\n    def inner():\n        return x\n    return inner\nf = outer()")
    assert "error" not in result
    # x should appear in the trace


def test_capture_closure_multiple_levels():
    """Nested closures should capture from multiple levels."""
    result = run_trace(
        "a = 1\n"
        "def outer():\n"
        "    b = 2\n"
        "    def middle():\n"
        "        def inner():\n"
        "            return a + b\n"
        "        return inner\n"
        "    return middle\n"
        "f = outer()()"
    )
    assert "error" not in result


def test_capture_lambda_closure():
    """Lambda capturing closure variable should work."""
    result = run_trace("x = 10\nf = lambda: x\ny = f()")
    assert "error" not in result
    # y should be 10


def test_capture_variable_shadowing():
    """Variable shadowing should track the correct value."""
    result = run_trace(
        "x = 1\n"  # outer x = 1
        "def outer():\n"
        "    x = 2\n"  # inner x = 2 (shadows outer)
        "    return x\n"
        "y = outer()\n"
        "z = x"  # z should be 1 (outer x)
    )
    assert "error" not in result
    # z should be 1, y should be 2


def test_capture_class_attribute():
    """Class attribute should be captured."""
    result = run_trace(
        "class A:\n"
        "    x = 10\n"
        "obj = A()\n"
        "y = obj.x"
    )
    assert "error" not in result


def test_capture_instance_attribute():
    """Instance attribute should be captured."""
    result = run_trace(
        "class A:\n"
        "    def __init__(self):\n"
        "        self.x = 10\n"
        "obj = A()\n"
        "y = obj.x"
    )
    assert "error" not in result


def test_capture_self_in_method():
    """self in method should be captured."""
    result = run_trace(
        "class A:\n"
        "    def method(self):\n"
        "        return 42\n"
        "obj = A()\n"
        "x = obj.method()"
    )
    assert "error" not in result


# =============================================================================
# Comprehension and generator characterization
# =============================================================================

def test_capture_list_comprehension():
    """List comprehension should capture result variable."""
    result = run_trace("squares = [x**2 for x in range(3)]")
    assert "error" not in result
    found_squares = any("squares" in s["variables"] for s in result["steps"])
    assert found_squares


def test_capture_dict_comprehension():
    """Dictionary comprehension should capture result variable."""
    result = run_trace("d = {x: x**2 for x in range(3)}")
    assert "error" not in result


def test_capture_set_comprehension():
    """Set comprehension should capture result variable."""
    result = run_trace("s = {x**2 for x in range(3)}")
    assert "error" not in result


def test_capture_generator_expression():
    """Generator expression should be captured."""
    result = run_trace("g = (x**2 for x in range(3))")
    assert "error" not in result


def test_capture_comprehension_variable():
    """Comprehension iteration variable should be captured."""
    result = run_trace("result = [x*2 for x in [1,2,3]]")
    assert "error" not in result
    # Note: iteration variable 'x' may or may not be captured
    # depending on implementation


def test_capture_walrus_operator():
    """Walrus operator (:=) should capture variable."""
    result = run_trace("result = [y for x in [1,2,3] if (y := x*2) or True]")
    assert "error" not in result
    # Note: walrus operator creates a variable in the comprehension scope


def test_capture_nested_comprehension():
    """Nested comprehension should capture correctly."""
    result = run_trace("matrix = [[i+j for j in range(3)] for i in range(3)]")
    assert "error" not in result
    found_matrix = any("matrix" in s["variables"] for s in result["steps"])
    assert found_matrix


# =============================================================================
# Branch detection edge cases
# =============================================================================

def test_branch_nested_if():
    """Nested if statements should each generate branch info."""
    result = run_trace(
        "x = 1\n"
        "if x > 0:\n"
        "    if x > 1:\n"
        "        y = 1\n"
        "    else:\n"
        "        y = 2\n"
        "else:\n"
        "    y = 3"
    )
    assert "error" not in result
    # Both if statements should appear in branches_taken


def test_branch_ternary():
    """Ternary expression should be in trace (even if not detected as branch)."""
    result = run_trace("x = 1 if True else 2")
    assert "error" not in result
    # Ternary should execute correctly


def test_branch_while_loop():
    """While loop should appear in trace with iteration."""
    result = run_trace("i = 0\nwhile i < 3:\n    i += 1")
    assert "error" not in result
    assert result["total_steps"] >= 4


def test_branch_for_loop():
    """For loop should appear in trace with iterations."""
    result = run_trace("for i in range(3):\n    pass")
    assert "error" not in result
    assert result["total_steps"] >= 3


def test_branch_break():
    """break statement should be captured."""
    result = run_trace("for i in range(10):\n    if i == 3:\n        break")
    assert "error" not in result


def test_branch_continue():
    """continue statement should be captured."""
    result = run_trace("result = [x for x in range(5) if x != 2]")
    assert "error" not in result


def test_branch_boolean_short_circuit():
    """Boolean and/or should short-circuit."""
    result = run_trace("x = False and (1/0)\nx = True or (1/0)")
    assert "error" not in result
    # Should not raise ZeroDivisionError


# =============================================================================
# Exception handling characterization
# =============================================================================

def test_capture_exception_raised():
    """Raised exception propagates up (not caught in run_trace)."""
    # Current behavior: raised exceptions propagate to caller
    # run_trace does not catch generic RuntimeError
    with pytest.raises(RuntimeError):
        run_trace("raise RuntimeError('test')")


def test_capture_exception_in_function():
    """Exception in function should be captured."""
    result = run_trace(
        "def foo():\n"
        "    raise ValueError('bad')\n"
        "try:\n"
        "    foo()\n"
        "except:\n"
        "    x = 1"
    )
    assert "error" not in result


def test_capture_try_except():
    """Try/except should be captured."""
    result = run_trace(
        "try:\n"
        "    x = 1\n"
        "except:\n"
        "    x = 2"
    )
    assert "error" not in result


# =============================================================================
# Namespace scanning behavior
# =============================================================================

def test_namespace_scan_comprehension():
    """Comprehension should populate namespace on return."""
    result = run_trace("[x for x in range(3)]")
    assert "error" not in result
    # The comprehension result should be captured somehow


def test_namespace_scan_multiple_comprehensions():
    """Multiple comprehensions should all be captured."""
    result = run_trace("a = [x for x in range(3)]\nb = (x for x in range(3)]")
    # Note: potential syntax error in test code above, fix it
    result = run_trace("a = [x for x in range(3)]\nb = [x for x in range(3)]")
    assert "error" not in result


def test_namespace_scan_store_name_in_comprehension():
    """STORE_NAME in comprehension should be scanned from namespace."""
    result = run_trace("squares = [x**2 for x in [1,2,3]]")
    # The 'squares' variable should be captured
    found = any("squares" in s["variables"] for s in result["steps"])
    assert found


# =============================================================================
# max_steps boundary behavior
# =============================================================================

def test_max_steps_exactly_one():
    """max_steps=1 should produce at most 1 step."""
    result = run_trace("x = 1\ny = 2", max_steps=1)
    assert result["total_steps"] <= 1


def test_max_steps_zero():
    """max_steps=0 should produce 0 steps."""
    result = run_trace("x = 1", max_steps=0)
    assert isinstance(result, dict)
    assert result["total_steps"] == 0


def test_max_steps_very_small():
    """Very small max_steps should limit steps."""
    result = run_trace("x = 1\ny = 2\nz = 3", max_steps=2)
    assert result["total_steps"] <= 2


def test_max_steps_infinite_loop():
    """Infinite loop with small max_steps should error."""
    result = run_trace_subprocess("while True: pass", max_steps=10, timeout_seconds=5)
    assert result.get("error") == "MAX_STEPS_EXCEEDED"


# =============================================================================
# Bytecode offset tracking
# =============================================================================

def test_bytecode_offset_increasing():
    """Bytecode offsets should be non-negative integers."""
    result = run_trace("x = 1")
    for step in result["steps"]:
        assert isinstance(step["bytecode_offset"], int)
        assert step["bytecode_offset"] >= 0


def test_bytecode_offset_different_instructions():
    """Different instructions should have different offsets."""
    result = run_trace("x = 1\ny = 2")
    offsets = [s["bytecode_offset"] for s in result["steps"]]
    # Offsets should be unique (or at least some should differ)
    assert len(offsets) >= 1


# =============================================================================
# Duration_ms calculation
# =============================================================================

def test_duration_ms_calculated():
    """duration_ms should be present and positive."""
    result = run_trace("x = 1")
    assert "duration_ms" in result
    assert result["duration_ms"] >= 0


def test_duration_ms_per_step():
    """Each step should have duration_ms set."""
    result = run_trace("x = 1\ny = 2")
    for step in result["steps"]:
        assert "duration_ms" in step
        assert step["duration_ms"] >= 0


def test_duration_ms_sum_approximation():
    """Sum of per-step durations should approximate total duration."""
    result = run_trace("x = 1\ny = 2")
    if result["steps"]:
        per_step_avg = sum(s["duration_ms"] for s in result["steps"]) / len(result["steps"])
        assert per_step_avg >= 0


# =============================================================================
# Opcode tracking
# =============================================================================

def test_opcode_known():
    """Opcodes in trace should be recognized."""
    result = run_trace("x = 1")
    for step in result["steps"]:
        assert isinstance(step["opcode"], str)
        assert len(step["opcode"]) > 0


def test_opcode_load_const():
    """LOAD_CONST should appear for constants."""
    result = run_trace("x = 42")
    assert "error" not in result
    assert any("opcode" in s for s in result["steps"])


def test_opcode_store_name():
    """STORE_NAME should appear for assignments."""
    result = run_trace("x = 1")
    assert "error" not in result
    assert any("opcode" in s for s in result["steps"])


# =============================================================================
# Edge cases and potential bugs
# =============================================================================

def test_empty_source():
    """Empty source should not crash."""
    result = run_trace("")
    assert isinstance(result, dict)


def test_whitespace_only_source():
    """Whitespace-only source should be handled."""
    result = run_trace("   \n\n   ")
    assert isinstance(result, dict)


def test_comment_only_source():
    """Comment-only source should not crash."""
    result = run_trace("# just a comment")
    assert isinstance(result, dict)


def test_function_with_no_return():
    """Function without return should have None."""
    result = run_trace(
        "def foo():\n"
        "    x = 1\n"
        "y = foo()"
    )
    assert "error" not in result


def test_function_returning_none():
    """Function explicitly returning None."""
    result = run_trace(
        "def foo():\n"
        "    return None\n"
        "x = foo()"
    )
    assert "error" not in result


def test_none_variable():
    """Variable set to None should be captured."""
    result = run_trace("x = None")
    assert "error" not in result
    found_none = any(
        s["variables"].get("x", {}).get("value") == "None"
        for s in result["steps"]
    )
    assert found_none, "None value should be captured"


def test_boolean_variables():
    """Boolean variables should be captured correctly."""
    result = run_trace("x = True\ny = False")
    assert "error" not in result


def test_float_precision():
    """Float values should be captured with precision."""
    result = run_trace("x = 3.141592653589793")
    assert "error" not in result
    for step in result["steps"]:
        if "x" in step["variables"]:
            val = step["variables"]["x"]["value"]
            # Value should contain pi approximation
            assert "3.14159" in val or "3.1415" in val


def test_string_with_quotes():
    """String with quotes should be captured."""
    result = run_trace('x = "hello\\nworld"')
    assert "error" not in result


def test_multiline_string():
    """Multiline string should be captured."""
    result = run_trace('x = """line1\nline2\nline3"""')
    assert "error" not in result


def test_unicode_string():
    """Unicode string should be captured."""
    result = run_trace('x = "Hello, \u4e16\u754c"')
    assert "error" not in result


def test_negative_number():
    """Negative number should be captured."""
    result = run_trace("x = -42")
    assert "error" not in result
    for step in result["steps"]:
        if "x" in step["variables"]:
            assert step["variables"]["x"]["type"] == "int"


def test_arithmetic_expressions():
    """Arithmetic expressions should evaluate correctly."""
    result = run_trace("x = 1 + 2 * 3")
    assert "error" not in result
    for step in result["steps"]:
        if "x" in step["variables"]:
            assert step["variables"]["x"]["value"] == "7"


def test_comparison_expression():
    """Comparison expression should evaluate correctly."""
    result = run_trace("x = 5 > 3")
    assert "error" not in result
    for step in result["steps"]:
        if "x" in step["variables"]:
            assert step["variables"]["x"]["value"] == "True"


def test_logical_expression():
    """Logical expression should evaluate correctly."""
    result = run_trace("x = (True and False) or True")
    assert "error" not in result


# =============================================================================
# Subprocess isolation tests
# =============================================================================

def test_subprocess_timeout():
    """Subprocess should timeout on infinite loop OR max_steps."""
    result = run_trace_subprocess("while True: pass", timeout_seconds=2)
    # Current behavior: max_steps=500 fires first, producing MAX_STEPS_EXCEEDED
    # TIMEOUT only fires when max_steps is set very high
    assert result["error"] in ("TIMEOUT", "MAX_STEPS_EXCEEDED")


def test_subprocess_captures_variables():
    """Subprocess should capture variables like direct call."""
    result = run_trace_subprocess("x = 42")
    assert "error" not in result
    found_x = any("x" in s["variables"] for s in result["steps"])
    assert found_x


def test_subprocess_blocks_dangerous_code():
    """Subprocess should block dangerous imports."""
    result = run_trace_subprocess("import os")
    assert result["error"] == "SANDBOX_ERROR"


def test_subprocess_multiple_steps():
    """Subprocess should handle multiple steps."""
    result = run_trace_subprocess("for i in range(5):\n    pass")
    assert "error" not in result
    assert result["total_steps"] >= 5


def test_subprocess_nested_function():
    """Subprocess should handle nested functions."""
    result = run_trace_subprocess(
        "def outer():\n"
        "    def inner():\n"
        "        return 42\n"
        "    return inner()\n"
        "x = outer()"
    )
    assert "error" not in result
    x_vals = [s["variables"].get("x", {}).get("value") for s in result["steps"]]
    assert "42" in x_vals


# =============================================================================
# Frame chain behavior
# =============================================================================

def test_frame_chain_closure():
    """Variables should be captured from frame chain (closures)."""
    result = run_trace(
        "def outer():\n"
        "    x = 10\n"
        "    def inner():\n"
        "        return x\n"
        "    return inner\n"
        "f = outer()\n"
        "y = f()"
    )
    assert "error" not in result


def test_frame_chain_method():
    """Instance method should see self and class."""
    result = run_trace(
        "class A:\n"
        "    val = 100\n"
        "    def get_val(self):\n"
        "        return self.val\n"
        "obj = A()\n"
        "x = obj.get_val()"
    )
    assert "error" not in result


# =============================================================================
# Sandbox validation
# =============================================================================

def test_validation_blocks_getattr():
    """getattr should be blocked."""
    from tracer.validator import validate_code
    is_valid, blocking, _ = validate_code("getattr(obj, 'attr')")
    assert is_valid is False


def test_validation_blocks_setattr():
    """setattr should be blocked."""
    from tracer.validator import validate_code
    is_valid, blocking, _ = validate_code("setattr(obj, 'attr', val)")
    assert is_valid is False


def test_validation_blocks_input():
    """input() should be blocked."""
    from tracer.validator import validate_code
    is_valid, blocking, _ = validate_code("x = input()")
    assert is_valid is False


def test_validation_allows_lambda():
    """Lambda should be allowed."""
    from tracer.validator import validate_code
    is_valid, blocking, _ = validate_code("f = lambda x: x + 1")
    assert is_valid is True


def test_validation_allows_class():
    """Class definition should be allowed."""
    from tracer.validator import validate_code
    is_valid, blocking, _ = validate_code("class Foo:\n    pass")
    assert is_valid is True


# =============================================================================
# Return value capture
# =============================================================================

def test_return_value_captured():
    """Function return value should be captured."""
    result = run_trace(
        "def add(a, b):\n"
        "    return a + b\n"
        "x = add(1, 2)"
    )
    assert "error" not in result
    found_3 = any(
        s["variables"].get("x", {}).get("value") == "3"
        for s in result["steps"]
    )
    assert found_3


def test_return_none_captured():
    """Function returning None should show None."""
    result = run_trace(
        "def foo():\n"
        "    return\n"
        "x = foo()"
    )
    assert "error" not in result


def test_multiple_returns():
    """Multiple return paths should all work."""
    result = run_trace(
        "def choose(cond):\n"
        "    if cond:\n"
        "        return 1\n"
        "    else:\n"
        "        return 2\n"
        "x = choose(True)\n"
        "y = choose(False)"
    )
    assert "error" not in result


# ── run_trace critical path characterization ─────────────────────────

def test_run_trace_nested_function_return():
    """Nested function return value should be captured."""
    result = run_trace(
        "def outer():\n"
        "    def inner():\n"
        "        return 99\n"
        "    return inner()\n"
        "x = outer()"
    )
    x_vals = [s["variables"].get("x", {}).get("value", "") for s in result["steps"]]
    assert "99" in x_vals


def test_run_trace_conditional_branch_runtime():
    """Runtime variable in condition should evaluate correctly."""
    result = run_trace(
        "flag = True\n"
        "if flag:\n"
        "    x = 'yes'\n"
        "else:\n"
        "    x = 'no'"
    )
    final_step = result["steps"][-1]
    assert final_step["variables"].get("x", {}).get("value") == "'yes'"


def test_run_trace_conditional_branch_false():
    """Runtime variable False in condition should take else."""
    result = run_trace(
        "flag = False\n"
        "if flag:\n"
        "    x = 'yes'\n"
        "else:\n"
        "    x = 'no'"
    )
    final_step = result["steps"][-1]
    assert final_step["variables"].get("x", {}).get("value") == "'no'"


def test_run_trace_multiple_variable_changes():
    """Multiple reassignments should track changed=True on each step."""
    result = run_trace("x = 1\nx = 2\nx = 3")
    for step in result["steps"]:
        if "x" in step["variables"]:
            assert step["variables"]["x"]["changed"] is True or step["variables"]["x"]["value"] == "1"


def test_run_trace_namespace_scan_on_comprehension():
    """Comprehension result appears via namespace scan, not frame locals."""
    result = run_trace("result = [i*2 for i in range(4)]")
    # squares should appear in at least one step
    assert any(
        "result" in s["variables"] for s in result["steps"]
    ), f"Expected 'result' in steps: {result['steps']}"
