import sys
import ast
import time
import dis
import types
from tracer.models import TraceStep, VariableInfo, SandboxError
from tracer.validator import validate_code

_INTERNAL_NAMES = frozenset({
    "__builtins__",
    "source", "max_steps", "compiled", "start_time",
    "jump_map", "opcode_map", "prev_variables", "steps", "tracer_callback",
    "namespace", "seen_lines",
    # Internal functions and modules
    "run_trace",
})

# Filter patterns for internal/unwanted variables
def _is_internal_variable(name: str) -> bool:
    """Check if a variable name is internal and should be hidden."""
    # Filter dunder variables (__name__, __doc__, etc.)
    if name.startswith("__") and name.endswith("__"):
        return True
    # Filter single underscore prefixed (like _tracer)
    if name.startswith("_") and not name.startswith("__"):
        return True
    # Filter common Python stdlib imports
    if name in (
        "sys", "os", "time", "datetime", "json", "re", "math",
        "random", "collections", "itertools", "functools",
        "typing", "abc", "io", "copy", "pickle", "hashlib",
        "pathlib", "glob", "urllib", "html", "xml", "csv",
        "argparse", "logging", "traceback", "warnings",
        "enum", "types", "inspect", "dis", "ast", "gc",
    ):
        return True
    return False


class _MaxStepsReached(Exception):
    """Raised when execution exceeds max_steps limit."""


def _build_jump_map(source: str) -> dict[int, list[ast.AST]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    jump_map: dict[int, list[ast.AST]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.For, ast.While)):
            if hasattr(node, "test") and node.test:
                jump_map.setdefault(node.test.lineno, []).append(node)
        elif isinstance(node, ast.BoolOp):
            jump_map.setdefault(node.lineno, []).append(node)
    return jump_map


def _build_opcode_map(code: types.CodeType) -> dict[int, str]:
    return {instr.offset: instr.opname for instr in dis.get_instructions(code)}


def _get_call_depth(frame) -> int:
    depth = 0
    f = frame
    while f:
        if f.f_code.co_filename == "<codescope>":
            depth += 1
        f = f.f_back
    return max(1, depth)


def _capture_variables(
    frame: types.FrameType,
    prev_variables: dict[str, str],
    namespace: dict,
) -> dict[str, VariableInfo]:
    """Capture all user-relevant variables from frame chain and namespace."""
    variables: dict[str, VariableInfo] = {}

    # Walk entire frame chain (fixes closures + comprehension inner frames)
    scope: types.FrameType | None = frame
    while scope is not None:
        if scope.f_code.co_filename != "<codescope>":
            scope = scope.f_back
            continue
        for name in list(scope.f_locals.keys()):
            if name in _INTERNAL_NAMES or _is_internal_variable(name):
                continue
            try:
                val = scope.f_locals[name]
                prev_repr = prev_variables.get(name, None)
                curr_repr = repr(val)[:200]
                changed = (prev_repr is not None) and (curr_repr != prev_repr)
                if name not in variables:
                    variables[name] = VariableInfo(
                        type=type(val).__name__,
                        value=curr_repr,
                        changed=changed,
                    )
            except (NameError, RuntimeError, KeyError):
                pass
        scope = scope.f_back

    # On 'return' from comprehension/function, also scan the namespace dict
    # for names that haven't appeared in any frame yet (list comprehension
    # STORE_NAME happens at the end of the comprehension before its return)
    for name, val in namespace.items():
        if name in _INTERNAL_NAMES or _is_internal_variable(name):
            continue
        if name not in variables:
            prev_repr = prev_variables.get(name, None)
            curr_repr = repr(val)[:200]
            variables[name] = VariableInfo(
                type=type(val).__name__,
                value=curr_repr,
                changed=(prev_repr is not None) and (curr_repr != prev_repr),
            )

    # Add initial namespace variables that haven't appeared in any frame yet
    # (they exist at step 0 before the code runs)
    for name, val in namespace.items():
        if name in _INTERNAL_NAMES or _is_internal_variable(name):
            continue
        if name not in variables:
            prev_repr = prev_variables.get(name, None)
            curr_repr = repr(val)[:200]
            variables[name] = VariableInfo(
                type=type(val).__name__,
                value=curr_repr,
                changed=(prev_repr is not None) and (curr_repr != prev_repr),
            )

    return variables


def run_trace(
    source: str,
    max_steps: int = 500,
    initial_namespace: dict | None = None,
) -> dict:
    """
    Execute Python source code with step-by-step tracing.

    Args:
        source: Python source code string.
        max_steps: Maximum number of trace steps (default 500).
        initial_namespace: Optional dict of variable names → values to pre-populate
                          the execution namespace before code runs.
                          Values are evaluated as Python literals.
                          Example: {"items": [1, 2, 3], "threshold": 10}
    """
    jump_map = _build_jump_map(source)

    try:
        compiled = compile(source, "<codescope>", "exec")
    except SyntaxError as e:
        return {"error": "SYNTAX_ERROR", "message": str(e), "line": e.lineno}

    # Block dangerous side effects before execution
    is_valid, blocking, warnings = validate_code(source)
    if not is_valid:
        raise SandboxError(blocking[0]["pattern"] if blocking else "unknown")

    opcode_map = _build_opcode_map(compiled)

    steps: list[TraceStep] = []
    prev_variables: dict[str, str] = {}

    # Pre-populate namespace from initial_namespace if provided
    namespace: dict = {}
    if initial_namespace:
        for name, raw_val in initial_namespace.items():
            try:
                val = ast.literal_eval(repr(raw_val))
                namespace[name] = val
            except (ValueError, SyntaxError):
                pass  # Silently skip invalid initial values

    start_time = time.perf_counter()
    max_steps_reached = False

    def tracer_callback(frame, event, arg):
        nonlocal prev_variables

        # Only trace code in user space (<codescope>)
        if frame.f_code.co_filename != "<codescope>":
            return None if event == "return" else tracer_callback

        if len(steps) >= max_steps:
            nonlocal max_steps_reached
            max_steps_reached = True
            raise _MaxStepsReached

        # Handle 'line' events — step-by-step execution
        if event == "line":
            bytecode_offset = frame.f_lasti
            opcode = opcode_map.get(bytecode_offset, "UNKNOWN")
            line_no = frame.f_lineno

            variables = _capture_variables(frame, prev_variables, namespace)

            # Branch detection — evaluate the condition at runtime
            branches_taken: dict = {}
            if line_no in jump_map:
                for node in jump_map[line_no]:
                    if isinstance(node, ast.If):
                        try:
                            if sys.version_info >= (3, 9):
                                condition_expr = ast.unparse(node.test)
                            else:
                                # Fallback for Python < 3.9
                                condition_expr = f"<condition on line {node.test.lineno}>"
                            
                            # SAFETY: This eval() runs inside the already-sandboxed
                            # subprocess spawned by runner.py — NOT in the FastAPI
                            # process. The validator has already blocked dangerous
                            # builtins before we reach this point.
                            # LIMITATION: Conditions with side effects (e.g.
                            # counter.increment()) execute twice — once by exec(),
                            # once by eval() here. Acceptable for read-only tracing.
                            result = eval(condition_expr, namespace)  # noqa: S307
                            branches_taken["if"] = {
                                "taken": bool(result),
                                "line": line_no,
                                "branch": "then" if result else "else",
                                "condition": condition_expr,
                            }
                        except Exception:
                            branches_taken["if"] = {"taken": None, "line": line_no, "error": "could_not_evaluate"}

            is_generator = bool(frame.f_code.co_flags & 0x20)

            step = TraceStep(
                step_number=len(steps),
                line_number=line_no,
                bytecode_offset=bytecode_offset,
                opcode=opcode,
                variables=variables,
                branches_taken=branches_taken,
                duration_ms=0.0,
                call_depth=_get_call_depth(frame),
            )
            steps.append(step)
            prev_variables = {k: v.value for k, v in variables.items()}

            if event == "return" and not is_generator:
                return None

            return tracer_callback

        # Handle 'return' events — capture the final state of the namespace
        # This is how list comprehensions expose their result variable
        elif event == "return":
            variables = _capture_variables(frame, prev_variables, namespace)

            step = TraceStep(
                step_number=len(steps),
                line_number=frame.f_lineno,
                bytecode_offset=frame.f_lasti,
                opcode="RETURN_VALUE",
                variables=variables,
                branches_taken={},
                duration_ms=0.0,
                call_depth=_get_call_depth(frame),
            )
            steps.append(step)
            prev_variables = {k: v.value for k, v in variables.items()}
            return None

        return tracer_callback

    sys.settrace(tracer_callback)
    try:
        exec(compiled, namespace, namespace)
    except _MaxStepsReached:
        pass
    except SystemExit:
        pass
    except Exception as e:
        # Catch unexpected exceptions in codescope execution and report them gracefully
        import traceback
        tb = sys.exc_info()[2]
        
        # Locate frame inside user code
        exc_frame = None
        curr_tb = tb
        while curr_tb:
            if curr_tb.tb_frame.f_code.co_filename == "<codescope>":
                exc_frame = curr_tb.tb_frame
            curr_tb = curr_tb.tb_next
            
        line_no = exc_frame.f_lineno if exc_frame is not None else (steps[-1].line_number if steps else 1)
        
        # Capture variables at point of exception
        variables = {}
        if exc_frame:
            variables = _capture_variables(exc_frame, prev_variables, namespace)
            
        step = TraceStep(
            step_number=len(steps),
            line_number=line_no,
            bytecode_offset=exc_frame.f_lasti if exc_frame else 0,
            opcode="EXCEPTION",
            variables=variables,
            branches_taken={"exception": {"type": type(e).__name__, "message": str(e)}},
            duration_ms=0.0,
            call_depth=_get_call_depth(exc_frame) if exc_frame else 1,
            exception_info=f"{type(e).__name__}: {str(e)}",
        )
        steps.append(step)
    finally:
        sys.settrace(None)

    duration_ms = (time.perf_counter() - start_time) * 1000
    if steps:
        # TODO: Replace uniform distribution with actual per-step timing.
        # To do this, capture time.perf_counter() at the start and end of each
        # tracer_callback invocation and store it in TraceStep.duration_ms directly.
        # Current approach (total / count) is misleading — loops appear to take the
        # same time as assignments.
        per_step = duration_ms / len(steps)
        for step in steps:
            step.duration_ms = round(per_step, 3)

    result = {
        "steps": [_step_to_dict(s) for s in steps],
        "total_steps": len(steps),
        "duration_ms": round(duration_ms, 2),
    }

    if max_steps_reached:
        result["error"] = "MAX_STEPS_EXCEEDED"
        result["message"] = f"Execution stopped after {max_steps} steps"

    return result


def _step_to_dict(step: TraceStep) -> dict:
    d = {
        "step_number": step.step_number,
        "line_number": step.line_number,
        "bytecode_offset": step.bytecode_offset,
        "opcode": step.opcode,
        "variables": {
            name: {"type": v.type, "value": v.value, "changed": v.changed}
            for name, v in step.variables.items()
        },
        "branches_taken": step.branches_taken,
        "duration_ms": step.duration_ms,
        "call_depth": step.call_depth,
    }
    if step.exception_info:
        d["exception_info"] = step.exception_info
    return d
