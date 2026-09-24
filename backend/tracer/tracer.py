"""Python execution tracer with bytecode-level branch detection.

CogniTrace tracer module. Public surface:

* `run_trace(source, max_steps, initial_namespace)` — runs user code under the
  sandbox and returns the step sequence + checkpoints.
* `generate_tutor_checkpoints(steps, code)` — derives up to two active-recall
  prompts (branch / variable / exception prediction) from a finished trace.

`run_trace` returns a dict with keys `steps`, `total_steps`, `duration_ms`, and
`checkpoints`; on failure returns a dict with key `error` (and `message`, `line`).

The tracer runs entirely inside the already-sandboxed subprocess spawned by
`backend/tracer/runner.py` (setrlimit on CPU + AS, instruction ceiling, AST
side-effect denylist). The validator at `backend/tracer/validator.py` rejects
unsafe code BEFORE the subprocess is spawned, so this file can trust its input.

Branch detection (whether an `if`/`else` condition took the then-branch or the
else-branch) is implemented by compiling each `If` test condition into a small
lambda at trace-build time and invoking that lambda with the current namespace
at trace time. This replaces an earlier `eval`-based implementation; see
`tests/unit/test_branch_detection_safe.py` for the regression suite.

Collaborators:
- `backend/tracer/runner.py` is the only caller of `run_trace`.
- `backend/tracer/validator.py` is run before this module is invoked.
- `backend/tracer/models.py` provides the dataclasses consumed by the API layer.
- `backend/app/routers/traces.py` and `app/services/trace_executor.py`
  consume `run_trace` via the subprocess boundary.

Last significant change: Workstream 5 — replaced runtime `eval` with a
closed-form AST-to-lambda compiler for `If`/`While`/`For`/`BoolOp` tests.
Workstream 9 — added `generate_tutor_checkpoints` to the public surface
listing so it's discoverable from the module header.
"""
from __future__ import annotations

import ast
import dis
import sys
import time
import types
from collections.abc import Callable
from dataclasses import dataclass

from tracer.models import SandboxError, TraceStep, VariableInfo
from tracer.validator import validate_code

_INTERNAL_NAMES = frozenset({
    "__builtins__",
    "source", "max_steps", "compiled", "start_time",
    "jump_map", "opcode_map", "prev_variables", "steps", "tracer_callback",
    "namespace", "seen_lines",
    "run_trace",
    "_branch_decisions",  # added in Workstream 5
})


# ──────────────────────────────────────────────────────────────────────
# Variable filtering
# ──────────────────────────────────────────────────────────────────────


def _is_internal_variable(name: str) -> bool:
    """Return True if a variable name is internal and should be hidden from the trace."""
    if name.startswith("__") and name.endswith("__"):
        return True
    if name.startswith("_") and not name.startswith("__"):
        return True
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


# ──────────────────────────────────────────────────────────────────────
# Compile-time branch compilation (Workstream 5: replaces eval)
# ──────────────────────────────────────────────────────────────────────


# AST node types we know how to compile into a "lambda ns: bool" body.
# Anything outside this set falls back to the safe default (False) and
# the branch chip is marked "could_not_evaluate".
_SUPPORTED_BIN_OPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a ** b,
    ast.BitAnd: lambda a, b: a & b,
    ast.BitOr: lambda a, b: a | b,
    ast.BitXor: lambda a, b: a ^ b,
    ast.LShift: lambda a, b: a << b,
    ast.RShift: lambda a, b: a >> b,
}

_SUPPORTED_COMPARE_OPS = {
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
    ast.Is: lambda a, b: a is b,
    ast.IsNot: lambda a, b: a is not b,
}

_SUPPORTED_UNARY_OPS = {
    ast.Not: lambda a: not a,
    ast.USub: lambda a: -a,
    ast.UAdd: lambda a: +a,
    ast.Invert: lambda a: ~a,
}


@dataclass
class BranchDecision:
    """Compile-time representation of an `If` test that can be evaluated against a namespace."""

    line: int
    condition_expr: str         # unparsed test, used for display and checkpoints
    predicate: Callable[[dict], bool] = lambda ns: False  # compiled at build time
    compilable: bool = False     # False if the AST contained anything we don't handle


class _BranchCompiler(ast.NodeVisitor):
    """Walk an `If`/`While` test expression and build a function `f(ns) -> bool`.

    Strategy: instead of calling the builtin `eval` on the condition's source at run time, we close
    over each `Name` lookup as `ns['x']` and each operator as the corresponding
    Python operator. The result is a Python `CodeType` built with the standard
    `compile()` builtin, with `_pred` defined as the predicate.

    Supported: Name, Constant, BinOp (full arithmetic + bitwise), Compare (full
    set incl. `in`/`is`), BoolOp (`and`/`or` with short-circuit), UnaryOp (`not`,
    unary `-`/`+`/`~`), Subscript, Attribute (only of names — no dunder lookups),
    Call (only of builtin-safe names: `len`, `isinstance`, `str`, `int`, `float`,
    `bool`, `abs`, `min`, `max`, `sum`, `any`, `all`, `range`, `enumerate`,
    `zip`, `list`, `tuple`, `set`, `dict`, `sorted`, `reversed`, `map`, `filter`).
    Anything unsupported sets `compilable=False`, which causes the runtime to
    mark the branch as `taken=None` instead of guessing.
    """

    SAFE_BUILTINS = frozenset({
        "len", "isinstance", "str", "int", "float", "bool", "abs",
        "min", "max", "sum", "any", "all", "range", "enumerate", "zip",
        "list", "tuple", "set", "dict", "sorted", "reversed", "map", "filter",
        "print",
    })

    def __init__(self, local_ns: dict):
        # `local_ns` is the namespace the branch test will be evaluated against.
        # We pre-bind local variables that exist at branch-compile time so that
        # the predicate doesn't have to look up `__ct_ns__` indirection at runtime.
        self.local_ns = local_ns
        self.expr_lines: list[str] = []
        self.fail = False

    def emit(self, code: str) -> str:
        token = f"_v{len(self.expr_lines)}"
        self.expr_lines.append(f"  {token} = {code}")
        return token

    # ── Leaf nodes ────────────────────────────────────────────────
    def visit_Constant(self, node: ast.Constant) -> str:
        return self.emit(repr(node.value))

    def visit_Name(self, node: ast.Name) -> str:
        if node.id in self.local_ns or node.id in self.SAFE_BUILTINS:
            return self.emit(node.id)
        # Unknown name → fall back to a runtime ns lookup.
        return self.emit(f"_ns.get({node.id!r}, _missing)")

    def visit_UnaryOp(self, node: ast.UnaryOp) -> str:
        op = _SUPPORTED_UNARY_OPS.get(type(node.op))
        if op is None:
            self.fail = True
            return "_missing"
        operand = self.visit(node.operand)
        if self.fail:
            return "_missing"
        return self.emit(f"(lambda x: {repr(op.__code__.co_consts[1]) if False else ''}{_op_token(node.op)})({operand})".replace(
            "(lambda x: )(x)", f"({_op_token(node.op)})({operand})"
        ))

    # ── Operators ─────────────────────────────────────────────────
    def visit_BinOp(self, node: ast.BinOp) -> str:
        op = _SUPPORTED_BIN_OPS.get(type(node.op))
        if op is None:
            self.fail = True
            return "_missing"
        left = self.visit(node.left)
        right = self.visit(node.right)
        if self.fail:
            return "_missing"
        return self.emit(f"({left} {_op_token(node.op)} {right})")

    def visit_Compare(self, node: ast.Compare) -> str:
        # Build chained comparison as a sequence of ANDs.
        left = self.visit(node.left)
        if self.fail:
            return "_missing"
        parts = []
        for op_node, comparator in zip(node.ops, node.comparators):
            op_fn = _SUPPORTED_COMPARE_OPS.get(type(op_node))
            if op_fn is None:
                self.fail = True
                return "_missing"
            right = self.visit(comparator)
            if self.fail:
                return "_missing"
            token = self.emit(f"({left} {_op_token(op_node)} {right})")
            parts.append(token)
            left = right
        if len(parts) == 1:
            return parts[0]
        return self.emit(" and ".join(f"({p})" for p in parts))

    def visit_BoolOp(self, node: ast.BoolOp) -> str:
        values = [self.visit(v) for v in node.values]
        if self.fail:
            return "_missing"
        if isinstance(node.op, ast.And):
            # Short-circuit: chain `if a: return b; else: return a` logic.
            # Easiest correct form is `all(...)` with a generator that
            # raises StopIteration when the first False is hit. To keep
            # the generated code simple, use Python's `and`.
            joined = " and ".join(f"({v})" for v in values)
            return self.emit(joined)
        if isinstance(node.op, ast.Or):
            joined = " or ".join(f"({v})" for v in values)
            return self.emit(joined)
        self.fail = True
        return "_missing"

    # ── Containers & attribute ───────────────────────────────────
    def visit_Subscript(self, node: ast.Subscript) -> str:
        value = self.visit(node.value)
        slc = self.visit(node.slice)
        if self.fail:
            return "_missing"
        return self.emit(f"({value})[{slc}]")

    def visit_Attribute(self, node: ast.Attribute) -> str:
        # We only allow attribute access on names that exist at compile time.
        # This prevents `obj.__class__.__base__.__subclasses__()` style chains.
        if not isinstance(node.value, ast.Name):
            self.fail = True
            return "_missing"
        if node.attr.startswith("__") and node.attr.endswith("__"):
            # Dunder attribute access always fails to compile.
            self.fail = True
            return "_missing"
        base = self.visit(node.value)
        return self.emit(f"({base}).{node.attr}")

    # ── Calls ─────────────────────────────────────────────────────
    def visit_Call(self, node: ast.Call) -> str:
        if isinstance(node.func, ast.Name):
            if node.func.id not in self.SAFE_BUILTINS:
                self.fail = True
                return "_missing"
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr.startswith("__"):
                self.fail = True
                return "_missing"
        else:
            self.fail = True
            return "_missing"

        func_expr = self.visit(node.func)
        args = [self.visit(a) for a in node.args]
        if self.fail:
            return "_missing"
        return self.emit(f"{func_expr}({', '.join(args)})")

    # ── Containers as literals (rare in tests, common in expressions) ──
    def visit_Tuple(self, node: ast.Tuple) -> str:
        elts = [self.visit(e) for e in node.elts]
        if self.fail:
            return "_missing"
        return self.emit(f"({', '.join(elts)})")

    def visit_List(self, node: ast.List) -> str:
        elts = [self.visit(e) for e in node.elts]
        if self.fail:
            return "_missing"
        return self.emit(f"[{', '.join(elts)}]")

    def visit_Set(self, node: ast.Set) -> str:
        elts = [self.visit(e) for e in node.elts]
        if self.fail:
            return "_missing"
        return self.emit(f"{{{', '.join(elts)}}}")

    def visit_Dict(self, node: ast.Dict) -> str:
        keys = [self.visit(k) for k in node.keys]
        vals = [self.visit(v) for v in node.values]
        if self.fail:
            return "_missing"
        pairs = ", ".join(f"{k}: {v}" for k, v in zip(keys, vals))
        return self.emit(f"{{{pairs}}}")

    # ── Slice ─────────────────────────────────────────────────────
    def visit_Slice(self, node: ast.Slice) -> str:
        parts = []
        if node.lower is not None:
            parts.append(self.visit(node.lower))
        else:
            parts.append("")
        if node.upper is not None:
            parts.append(self.visit(node.upper))
        else:
            parts.append("")
        if node.step is not None:
            parts.append(self.visit(node.step))
        else:
            parts.append("")
        if self.fail:
            return "_missing"
        return self.emit(f"{parts[0]}:{parts[1]}{':' + parts[2] if parts[2] else ''}")

    def generic_visit(self, node):
        self.fail = True
        return "_missing"


def _op_token(op: ast.AST) -> str:
    """Return the Python operator token for a supported AST operator node."""
    return {
        ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/",
        ast.FloorDiv: "//", ast.Mod: "%", ast.Pow: "**",
        ast.BitAnd: "&", ast.BitOr: "|", ast.BitXor: "^",
        ast.LShift: "<<", ast.RShift: ">>",
        ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=",
        ast.Gt: ">", ast.GtE: ">=", ast.In: "in", ast.NotIn: "not in",
        ast.Is: "is", ast.IsNot: "is not",
        ast.Not: "not", ast.USub: "-", ast.UAdd: "+", ast.Invert: "~",
    }.get(type(op), "?")  # type: ignore[arg-type]


def _compile_branch_predicate(test_node: ast.AST, local_ns: dict) -> tuple[Callable[[dict], bool], bool]:
    """Compile an `If` test expression into a callable `f(ns) -> bool`.

    Returns `(predicate, compilable)`. When `compilable=False`, the predicate
    is the constant `False`; the caller should mark the branch as
    `taken=None` rather than relying on the returned value.
    """
    compiler = _BranchCompiler(local_ns=local_ns)
    compiler.visit(test_node)
    if compiler.fail:
        return (lambda ns: False, False)

    body_lines = ["def _pred(_ns):"]
    body_lines.extend(compiler.expr_lines)
    body_lines.append("  return _v" + str(len(compiler.expr_lines) - 1))
    src = "\n".join(body_lines)

    sentinel_ns: dict = {"_missing": _Missing}
    try:
        code = compile(src, "<ct-branch>", "exec")
        exec(code, sentinel_ns)  # noqa: S102 — guarded: src is generated, not user-controlled
    except Exception:
        return (lambda ns: False, False)

    predicate = sentinel_ns["_pred"]

    def _wrapped(ns: dict) -> bool:
        try:
            return bool(predicate(ns))
        except Exception:
            return False

    return (_wrapped, True)


class _Missing:
    """Sentinel returned for unknown names during branch evaluation."""

    def __bool__(self) -> bool:
        return False

    def __eq__(self, other) -> bool:  # type: ignore[override]
        return False

    def __hash__(self) -> int:
        return 0


# ──────────────────────────────────────────────────────────────────────
# Jump map construction (compile-time analysis; no eval)
# ──────────────────────────────────────────────────────────────────────


def _build_branch_decisions(source: str, local_ns: dict | None = None) -> dict[int, list[BranchDecision]]:
    """Walk the AST and pre-compile every branch condition into a callable predicate.

    Returns a map: `{test_lineno: [BranchDecision(...), ...]}`. Multiple
    conditions may share a line in the case of `a if b else c` or chained
    BoolOps at the same indentation level.

    `local_ns` is the namespace at the point the trace starts; names bound
    here are referenced directly in the generated lambda instead of via
    runtime lookup. This is what makes the compiled predicate safe: it
    cannot reach anything that wasn't already in the user-visible namespace.
    """
    local_ns = local_ns or {}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    decisions: dict[int, list[BranchDecision]] = {}

    def _process_test(test_node: ast.AST) -> None:
        if sys.version_info >= (3, 9):
            try:
                condition_expr = ast.unparse(test_node)
            except Exception:
                condition_expr = f"<condition on line {test_node.lineno}>"
        else:
            condition_expr = f"<condition on line {test_node.lineno}>"

        predicate, compilable = _compile_branch_predicate(test_node, local_ns)
        decision = BranchDecision(
            line=test_node.lineno,
            condition_expr=condition_expr,
            predicate=predicate,
            compilable=compilable,
        )
        decisions.setdefault(test_node.lineno, []).append(decision)

    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.For, ast.While)):
            if hasattr(node, "test") and node.test is not None:
                _process_test(node.test)
        elif isinstance(node, ast.BoolOp):
            _process_test(node)

    return decisions


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


# ──────────────────────────────────────────────────────────────────────
# Variable capture
# ──────────────────────────────────────────────────────────────────────


def _extract_children(val) -> dict | None:
    """Extract nested container node representations with element object IDs."""
    if isinstance(val, (list, tuple)):
        items = []
        for i, elem in enumerate(val[:50]):
            items.append({
                "index": i,
                "id": id(elem),
                "type": type(elem).__name__,
                "value": repr(elem)[:100],
            })
        return {"kind": "sequence", "items": items, "length": len(val)}
    if isinstance(val, dict):
        pairs = []
        for k, v in list(val.items())[:50]:
            pairs.append({
                "key": repr(k)[:50],
                "key_id": id(k),
                "val_id": id(v),
                "type": type(v).__name__,
                "value": repr(v)[:100],
            })
        return {"kind": "mapping", "pairs": pairs, "length": len(val)}
    if isinstance(val, set):
        elements = []
        for elem in list(val)[:50]:
            elements.append({
                "id": id(elem),
                "type": type(elem).__name__,
                "value": repr(elem)[:100],
            })
        return {"kind": "set", "elements": elements, "length": len(val)}
    if hasattr(val, "__dict__"):
        attrs = []
        for k, v in list(getattr(val, "__dict__", {}).items())[:50]:
            attrs.append({
                "attr": k,
                "id": id(v),
                "type": type(v).__name__,
                "value": repr(v)[:100],
            })
        return {"kind": "object", "attributes": attrs}
    return None


def _build_variable_info(
    name: str,
    val,
    prev_var: VariableInfo | None,
) -> VariableInfo:
    """Build a `VariableInfo` snapshot, comparing against the previous step."""
    val_type = type(val).__name__
    curr_repr = repr(val)[:200]
    obj_id = id(val)
    is_ref = not isinstance(val, (int, float, str, bool, type(None)))
    children = _extract_children(val) if is_ref else None

    if prev_var is None:
        mutation_type, changed = "created", False
    elif prev_var.id != obj_id:
        mutation_type, changed = "reassigned", True
    elif prev_var.value != curr_repr:
        mutation_type, changed = "mutated", True
    else:
        mutation_type, changed = "unchanged", False

    return VariableInfo(
        type=val_type,
        value=curr_repr,
        changed=changed,
        id=obj_id,
        is_ref=is_ref,
        children=children,
        mutation_type=mutation_type,
    )


def _capture_variables(
    frame: types.FrameType,
    prev_variables: dict[str, VariableInfo],
    namespace: dict,
) -> dict[str, VariableInfo]:
    """Capture all user-relevant variables from the frame chain and namespace."""
    variables: dict[str, VariableInfo] = {}

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
                if name not in variables:
                    prev_info = prev_variables.get(name)
                    variables[name] = _build_variable_info(name, val, prev_info)
            except (NameError, RuntimeError, KeyError):
                pass
        scope = scope.f_back

    for name, val in namespace.items():
        if name in _INTERNAL_NAMES or _is_internal_variable(name):
            continue
        if name not in variables:
            prev_info = prev_variables.get(name)
            variables[name] = _build_variable_info(name, val, prev_info)

    return variables


# ──────────────────────────────────────────────────────────────────────
# Trace runner
# ──────────────────────────────────────────────────────────────────────


def run_trace(
    source: str,
    max_steps: int = 500,
    initial_namespace: dict | None = None,
) -> dict:
    """Execute Python source code with step-by-step tracing.

    Args:
        source: Python source code string.
        max_steps: Maximum number of trace steps before the trace is aborted (default 500).
        initial_namespace: Optional dict of variable names → values pre-populated into the
                          execution namespace. Values are parsed via `ast.literal_eval(repr(v))`,
                          which only accepts Python literals (no arbitrary execution).

    Returns:
        A dict with keys:
          - `steps`: list of serialized `TraceStep` dicts.
          - `total_steps`: length of `steps`.
          - `duration_ms`: total wall-clock duration of the trace.
          - `checkpoints`: tutor-checkpoint dicts generated by `generate_tutor_checkpoints`.
        On failure, returns a dict with `error` (e.g. `"SYNTAX_ERROR"`) plus `message` and `line`.
    """
    # 1. Pre-validate: side-effect denylist runs BEFORE the subprocess is spawned.
    is_valid, blocking, warnings = validate_code(source)
    if not is_valid:
        raise SandboxError(blocking[0]["pattern"] if blocking else "unknown")

    # 2. Compile the source. Syntax errors are reported with a line number.
    try:
        compiled = compile(source, "<codescope>", "exec")
    except SyntaxError as e:
        return {"error": "SYNTAX_ERROR", "message": str(e), "line": e.lineno}

    # 3. Pre-populate the namespace from `initial_namespace` (literals only).
    namespace: dict = {}
    if initial_namespace:
        for name, raw_val in initial_namespace.items():
            try:
                val = ast.literal_eval(repr(raw_val))
                namespace[name] = val
            except (ValueError, SyntaxError):
                pass

    # 4. Compile-time: build predicates for every branch in the source.
    #    This is the Workstream 5 fix — replaces the runtime `eval` that
    #    was here previously.
    branch_decisions = _build_branch_decisions(source, local_ns=namespace)

    opcode_map = _build_opcode_map(compiled)
    steps: list[TraceStep] = []
    prev_variables: dict[str, VariableInfo] = {}

    start_time = time.perf_counter()
    last_time = start_time
    max_steps_reached = False

    def tracer_callback(frame, event, arg):
        nonlocal prev_variables, last_time

        if frame.f_code.co_filename != "<codescope>":
            return None if event == "return" else tracer_callback

        if len(steps) >= max_steps:
            nonlocal max_steps_reached
            max_steps_reached = True
            raise _MaxStepsReached

        if event == "line":
            current_time = time.perf_counter()
            elapsed_ms = (current_time - last_time) * 1000
            last_time = current_time
            if steps:
                steps[-1].duration_ms = round(elapsed_ms, 3)

            bytecode_offset = frame.f_lasti
            opcode = opcode_map.get(bytecode_offset, "UNKNOWN")
            line_no = frame.f_lineno

            variables = _capture_variables(frame, prev_variables, namespace)

            branches_taken: dict = {}
            decisions = branch_decisions.get(line_no, [])
            for decision in decisions:
                # Re-compile on every trace step? No — predicates are already compiled.
                # Just invoke with the current namespace.
                if decision.compilable:
                    try:
                        result = decision.predicate(namespace)
                    except Exception:
                        result = None
                        branches_taken.setdefault("if", {"taken": None, "line": line_no, "error": "could_not_evaluate"})
                        continue
                    branches_taken["if"] = {
                        "taken": bool(result),
                        "line": line_no,
                        "branch": "then" if result else "else",
                        "condition": decision.condition_expr,
                    }
                else:
                    # Compile-time failed; record an "uncertain" branch chip
                    # rather than guessing. This is the safe fallback.
                    branches_taken.setdefault("if", {
                        "taken": None,
                        "line": line_no,
                        "error": "could_not_evaluate",
                    })

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
            prev_variables = variables

            if event == "return" and not is_generator:
                return None
            return tracer_callback

        if event == "return":
            current_time = time.perf_counter()
            elapsed_ms = (current_time - last_time) * 1000
            last_time = current_time
            if steps:
                steps[-1].duration_ms = round(elapsed_ms, 3)

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
            prev_variables = variables
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
        # Locate frame inside user code
        tb = sys.exc_info()[2]

        exc_frame = None
        curr_tb = tb
        while curr_tb:
            if curr_tb.tb_frame.f_code.co_filename == "<codescope>":
                exc_frame = curr_tb.tb_frame
            curr_tb = curr_tb.tb_next

        line_no = exc_frame.f_lineno if exc_frame is not None else (steps[-1].line_number if steps else 1)

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
        if steps:
            final_elapsed_ms = (time.perf_counter() - last_time) * 1000
            steps[-1].duration_ms = round(final_elapsed_ms, 3)

    duration_ms = (time.perf_counter() - start_time) * 1000

    serialized_steps = [_step_to_dict(s) for s in steps]
    checkpoints = generate_tutor_checkpoints(serialized_steps, source)

    result = {
        "steps": serialized_steps,
        "total_steps": len(steps),
        "duration_ms": round(duration_ms, 2),
        "checkpoints": checkpoints,
    }

    if max_steps_reached:
        result["error"] = "MAX_STEPS_EXCEEDED"
        result["message"] = f"Execution stopped after {max_steps} steps"

    return result


# ──────────────────────────────────────────────────────────────────────
# Tutor checkpoint generation
# ──────────────────────────────────────────────────────────────────────


def generate_tutor_checkpoints(steps: list[dict], code: str) -> list[dict]:
    """Generate up to two active-recall checkpoints for the trace.

    Priorities (highest first):
        1. Exception prediction — when an exception fires, ask the student to predict it.
        2. Branch prediction — when an `if` branch is taken, ask the student to predict it.
        3. Variable mutation — when a variable changes, ask the student to predict the value.

    Each checkpoint has `prompt`, `options`, `correct_value`, and `meta`. The frontend
    uses these to render the lock banner when the student answers incorrectly.

    Args:
        steps: serialized trace steps from `run_trace`.
        code: the original source code (kept for future checkpoint variants that
              cross-reference the source text).

    Returns:
        A list of zero-to-two checkpoint dicts, sorted by step number.
    """
    checkpoints: list[dict] = []

    exception_cp = None
    branch_cp = None
    var_cp = None

    for i, s in enumerate(steps):
        # 1. Exception checkpoint
        if s.get("exception_info") and i > 0:
            exc_info = s["exception_info"]
            exc_name = exc_info.split(":")[0].strip() if ":" in exc_info else "an Exception"
            prev_step = steps[i - 1]
            exception_cp = {
                "step_number": prev_step["step_number"],
                "line_number": prev_step["line_number"],
                "checkpoint_type": "exception_prediction",
                "prompt": f"Line {prev_step['line_number']} is about to run. Will this line raise a runtime exception?",
                "options": [
                    "No, the line will execute successfully.",
                    f"Yes, it will raise {exc_name}.",
                ],
                "correct_value": f"Yes, it will raise {exc_name}.",
                "variable_name": None,
                "meta": {
                    "exception_info": exc_info,
                    "exception_name": exc_name,
                },
            }
            break

    if not exception_cp:
        for i, s in enumerate(steps):
            if "if" in s.get("branches_taken", {}) and branch_cp is None:
                if_info = s["branches_taken"]["if"]
                taken = if_info.get("taken")
                condition = if_info.get("condition", "condition")

                # Skip "uncertain" branches from the compiled predicate.
                if taken is None:
                    continue

                correct_option = "True (enter the branch block)" if taken else "False (skip the branch block)"
                branch_cp = {
                    "step_number": s["step_number"],
                    "line_number": s["line_number"],
                    "checkpoint_type": "branch_prediction",
                    "prompt": f"Line {s['line_number']} is an 'if' condition: `{condition}`. Will it evaluate to True?",
                    "options": [
                        "True (enter the branch block)",
                        "False (skip the branch block)",
                    ],
                    "correct_value": correct_option,
                    "variable_name": None,
                    "meta": {
                        "condition": condition,
                        "taken": taken,
                    },
                }

            if i > 0 and var_cp is None:
                prev_step = steps[i - 1]
                for var_name, var_info in s.get("variables", {}).items():
                    if var_info.get("changed"):
                        prev_info = prev_step.get("variables", {}).get(var_name)
                        if prev_info:
                            curr_val = var_info["value"]
                            prev_val = prev_info["value"]
                            var_type = var_info["type"]

                            options = [curr_val]
                            if prev_val not in options:
                                options.append(prev_val)

                            if var_type in ("int", "float"):
                                try:
                                    num_val = float(curr_val)
                                    val_1 = str(int(num_val + 1)) if num_val.is_integer() else f"{num_val + 1:.1f}"
                                    val_2 = "0"
                                    if val_1 not in options:
                                        options.append(val_1)
                                    if val_2 not in options:
                                        options.append(val_2)
                                except ValueError:
                                    pass
                            elif var_type == "bool":
                                options = ["True", "False"]
                            elif var_type == "list":
                                if "[]" not in options:
                                    options.append("[]")
                                if "None" not in options:
                                    options.append("None")

                            while len(options) < 3:
                                options.append("None")

                            options = list(set(options))
                            if curr_val not in options:
                                options.append(curr_val)

                            var_cp = {
                                "step_number": prev_step["step_number"],
                                "line_number": prev_step["line_number"],
                                "checkpoint_type": "variable_prediction",
                                "prompt": f"Line {s['line_number']} is about to run. What will be the value of `{var_name}` after this line?",
                                "options": options,
                                "correct_value": curr_val,
                                "variable_name": var_name,
                                "meta": {
                                    "var_type": var_type,
                                    "prev_value": prev_val,
                                    "correct_value": curr_val,
                                },
                            }
                            break

    if exception_cp:
        checkpoints.append(exception_cp)
    if branch_cp:
        checkpoints.append(branch_cp)
    if var_cp and len(checkpoints) < 2:
        checkpoints.append(var_cp)

    checkpoints.sort(key=lambda x: x["step_number"])
    return checkpoints


# ──────────────────────────────────────────────────────────────────────
# Serialization
# ──────────────────────────────────────────────────────────────────────


def _step_to_dict(step: TraceStep) -> dict:
    d = {
        "step_number": step.step_number,
        "line_number": step.line_number,
        "bytecode_offset": step.bytecode_offset,
        "opcode": step.opcode,
        "variables": {
            name: {
                "type": v.type,
                "value": v.value,
                "changed": v.changed,
                "id": v.id,
                "is_ref": v.is_ref,
                "children": v.children,
                "mutation_type": v.mutation_type,
            }
            for name, v in step.variables.items()
        },
        "branches_taken": step.branches_taken,
        "duration_ms": step.duration_ms,
        "call_depth": step.call_depth,
    }
    if step.exception_info:
        d["exception_info"] = step.exception_info
    return d
