from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Literal


@dataclass
class Annotation:
    line: int
    severity: Literal["high", "medium", "low"]
    pattern_id: str
    message: str
    suggestion: str


# ---------------------------------------------------------------------------
# Pattern 1: Missing None check before comparison
# AI often writes `if x:` or `if x == value:` without guarding against None.
# We flag bare `if name:` tests on variables used in the same scope.
# ---------------------------------------------------------------------------
def _check_missing_none_guard(node: ast.If, annotations: list[Annotation]) -> None:
    """
    Flag `if x == y:` / `if x < y:` without an explicit None guard.

    Note: bare `if x:` (Name node) is handled by `implicit_truthiness`.
    This function only handles Compare nodes and BoolOps containing Compare nodes.
    """
    test = node.test

    has_none_guard = False

    if isinstance(test, ast.Compare):
        has_none_guard = _has_none_guard_in_compare(test)
    elif isinstance(test, ast.BoolOp):
        for sub in ast.walk(test):
            if _has_none_guard_in_compare(sub):
                has_none_guard = True
    else:
        return  # bare name → implicit_truthiness

    if has_none_guard:
        return

    referenced: set[str] = set()

    class NameCollector(ast.NodeVisitor):
        def visit_Name(self, n: ast.Name) -> None:
            if isinstance(n.ctx, ast.Load):
                referenced.add(n.id)
            self.generic_visit(n)

    NameCollector().visit(test)

    for name in referenced:
        if not name.startswith("__"):
            annotations.append(
                Annotation(
                    line=node.lineno,
                    severity="high",
                    pattern_id="missing_none_guard",
                    message=(
                        f"`{name}` is compared directly — TypeError risk if `{name}` is None."
                    ),
                    suggestion=f"Add a guard: if {name} is not None and {name} ...",
                )
            )
            break


def _has_none_guard_in_compare(node: ast.AST) -> bool:
    """
    Return True if node is a Compare with `x is not None` or `x != None`.

    For `x is not None`:
      - left = Name('x')
      - ops = [IsNot()]
      - comparators = [Constant(value=None)]
    We need to check: the operator at position i is IsNot/NotEq AND
    the comparator at position i is a Constant None.
    """
    if not isinstance(node, ast.Compare):
        return False
    for op, comparator in zip(node.ops, node.comparators):
        if isinstance(op, (ast.IsNot, ast.NotEq)):
            if isinstance(comparator, ast.Constant) and comparator.value is None:
                return True
    return False


# ---------------------------------------------------------------------------
# Pattern 2: Mutable default argument
# def foo(items=[]) — the list is shared across all calls.
# ---------------------------------------------------------------------------
def _is_mutable_call(default: ast.expr) -> bool:
    """Return True if default is a call to list(), dict(), or set()."""
    if not isinstance(default, ast.Call):
        return False
    func = default.func
    return (
        isinstance(func, ast.Name)
        and func.id in ("list", "dict", "set", "frozenset")
    ) or (
        isinstance(func, ast.Attribute)
        and func.attr in ("list", "dict", "set", "frozenset")
    )


def _check_mutable_default(node: ast.FunctionDef, annotations: list[Annotation]) -> None:
    """Flag function arguments with mutable default values (list/dict/set literals or constructors)."""
    for arg, default in zip(reversed(node.args.args), reversed(node.args.defaults)):
        if isinstance(default, (ast.List, ast.Dict)):
            annotations.append(
                Annotation(
                    line=default.lineno,
                    severity="high",
                    pattern_id="mutable_default",
                    message=f"Mutable default argument `{arg.arg}=[...]` — the object is shared across all calls.",
                    suggestion=f"Use: def {node.name}({arg.arg}=None): ... if {arg.arg} is None: {arg.arg} = []",
                )
            )
        if isinstance(default, ast.Set) or _is_mutable_call(default):
            type_name = "set" if isinstance(default, ast.Set) else (
                default.func.id if isinstance(default.func, ast.Name) else default.func.attr
            )
            annotations.append(
                Annotation(
                    line=default.lineno,
                    severity="high",
                    pattern_id="mutable_default",
                    message=f"Mutable default argument `{arg.arg}={type_name}()` — the object is shared across all calls.",
                    suggestion=f"Use: def {node.name}({arg.arg}=None): ... if {arg.arg} is None: {arg.arg} = {type_name}()",
                )
            )
        # Flag ast.Constant wrapping a list/dict/set literal
        if isinstance(default, ast.Constant) and isinstance(default.value, (list, dict, set)):
            annotations.append(
                Annotation(
                    line=default.lineno,
                    severity="high",
                    pattern_id="mutable_default",
                    message=f"Mutable default argument `{arg.arg}={default.value!r}` — shared across all calls.",
                    suggestion=f"Use: def {node.name}({arg.arg}=None): ... if {arg.arg} is None: {arg.arg} = {type(default.value).__name__}()",
                )
            )


# ---------------------------------------------------------------------------
# Pattern 3: List comprehension with implicit filter that can empty the result
# [x for x in items if len(x) > 0] — if all items are empty, result is []
# More subtly: conditional that filters on a property that most items lack.
# ---------------------------------------------------------------------------
def _check_comprehension_filter(node: ast.ListComp, annotations: list[Annotation]) -> None:
    """Flag list comprehensions with an `if` clause that could filter everything."""
    has_filter = any(isinstance(gen, ast.comprehension) and gen.ifs for gen in node.generators)

    if not has_filter:
        return

    # Heuristic: the filter condition references something other than the main loop variable
    # and is a comparison — likely to silently produce [] for many inputs.
    for gen in node.generators:
        for if_clause in gen.ifs:
            # If the filter uses attribute access (e.g., x.strip()) it's more likely to
            # silently produce [] when strip() returns ""
            uses_attr = any(isinstance(sub, ast.Attribute) for sub in ast.walk(if_clause))
            if uses_attr:
                annotations.append(
                    Annotation(
                        line=node.lineno,
                        severity="medium",
                        pattern_id="comprehension_filter",
                        message="List comprehension `if` clause may filter all elements silently (e.g., `x.strip()` is falsy for whitespace-only strings).",
                        suggestion="Verify the filter handles empty/whitespace-only inputs. Consider: `if x and x.strip():`",
                    )
                )
                return

    # Fallback: flag comprehensions with multiple filters (common AI over-filtering)
    filter_count = sum(len(gen.ifs) for gen in node.generators)
    if filter_count > 1:
        annotations.append(
            Annotation(
                line=node.lineno,
                severity="medium",
                pattern_id="comprehension_filter",
                message=f"List comprehension has {filter_count} filter conditions — result may silently be empty.",
                suggestion="Verify all elements pass at least one filter. Consider adding a default case.",
            )
        )


# ---------------------------------------------------------------------------
# Pattern 4: Implicit truthiness check
# `if items:` — this is True for [], {}, 0, None, and non-empty collections.
# AI often intends to check "not empty" but the code says "is truthy".
# ---------------------------------------------------------------------------
_BOOLEAN_PREFIXES = ("is_", "has_", "have_", "does_", "did_", "will_", "should_", "can_")
_BOOLEAN_NAMES = frozenset({
    "true", "false", "flag", "enabled", "active", "ok", "done",
    "present", "available", "valid", "empty", "none", "null",
})


def _is_likely_boolean(name: str) -> bool:
    return (
        name.lower() in _BOOLEAN_NAMES
        or name.startswith(_BOOLEAN_PREFIXES)
    )


def _check_implicit_truthiness(node: ast.If, annotations: list[Annotation]) -> None:
    """Flag bare name conditions that rely on implicit truthiness (e.g., `if data:`)."""
    test = node.test

    # Only flag a bare Name in the test position
    if not isinstance(test, ast.Name):
        return

    name = test.id
    if _is_likely_boolean(name):
        return

    annotations.append(
        Annotation(
            line=node.lineno,
            severity="low",
            pattern_id="implicit_truthiness",
            message=(
                f"`if {name}:` is True for `{name}=[]`, `{name}={{}}`, "
                f"`{name}=0`, and `{name}=None` — not just when it has values."
            ),
            suggestion=f"Use explicit check: if {name} is not None and len({name}) > 0:",
        )
    )


# ---------------------------------------------------------------------------
# Pattern 5: requests call without timeout
# `requests.get(url)` with no timeout — blocks indefinitely on network failure.
# ---------------------------------------------------------------------------
def _check_requests_no_timeout(node: ast.Call, annotations: list[Annotation]) -> None:
    """Flag requests.get/post calls without a timeout argument."""
    # Only flag calls in the form: requests.<method>(...)
    # Not: session.get(), cache.get(), db.post(), etc.
    request_methods = ("get", "post", "put", "patch", "delete", "head", "options")
    func_name: str | None = None

    if not isinstance(node.func, ast.Attribute):
        return

    attr = node.func.attr
    if attr not in request_methods:
        return

    # Verify the object is literally named "requests" — not a session, client, etc.
    caller = node.func.value
    if not isinstance(caller, ast.Name) or caller.id != "requests":
        return

    func_name = attr

    # Check if 'timeout' is in the keyword arguments
    has_timeout = any(kw.arg == "timeout" for kw in node.keywords)

    if not has_timeout:
        annotations.append(
            Annotation(
                line=node.lineno,
                severity="high",
                pattern_id="requests_no_timeout",
                message=f"requests.{func_name}() has no timeout — will hang indefinitely on network failure.",
                suggestion="Add: timeout=5  (seconds). Or use: timeout=(3.05, 27) for (connect, read) timeout.",
            )
        )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def analyze_code(code: str) -> list[Annotation]:
    """
    Analyze Python source code and return a list of annotations for common AI bugs.

    Checks for:
      1. Missing None guard before comparison (TypeError risk)
      2. Mutable default arguments (shared state bug)
      3. List comprehension with aggressive filters (silent empty result)
      4. Implicit truthiness checks (wrong truthy/falsy behavior)
      5. requests calls without timeout (hang risk)
    """
    annotations: list[Annotation] = []

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return annotations

    for node in ast.walk(tree):
        # Pattern 2: Mutable default arguments (on FunctionDef before visiting children)
        if isinstance(node, ast.FunctionDef):
            _check_mutable_default(node, annotations)
            # Don't return early — continue to check inner code

        # Patterns 1 & 4: if/elif conditions
        if isinstance(node, ast.If):
            _check_missing_none_guard(node, annotations)
            _check_implicit_truthiness(node, annotations)

        # Pattern 3: List comprehensions
        if isinstance(node, ast.ListComp):
            _check_comprehension_filter(node, annotations)

        # Pattern 5: requests calls without timeout
        if isinstance(node, ast.Call):
            _check_requests_no_timeout(node, annotations)

    # Deduplicate by (line, pattern_id) — AST walk may visit the same node twice
    seen: set[tuple[int, str]] = set()
    unique: list[Annotation] = []
    for ann in annotations:
        key = (ann.line, ann.pattern_id)
        if key not in seen:
            seen.add(key)
            unique.append(ann)

    # Sort by line number
    unique.sort(key=lambda a: a.line)
    return unique
