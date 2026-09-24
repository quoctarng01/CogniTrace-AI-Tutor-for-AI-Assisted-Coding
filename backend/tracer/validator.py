"""Side-effect detection for user code validation using AST parsing.

CogniTrace validator. Public surface: `validate_code(source) -> (is_valid, blocking, warnings)`.

The validator is the FIRST line of defense against malicious user code. The dynamic
tracer (subprocess + setrlimit + sys.settrace) is the second. This file decides what
code is allowed to reach the subprocess at all.

Collaborators:
- `backend/tracer/runner.py` runs this before every trace.
- `backend/tracer/tracer.py` raises `SandboxError` if validation fails.
- Tests: `backend/tests/unit/test_validator.py` and `test_sandbox_bypass.py`.

Last significant change: Workstream 5 — added denylists for dunder attribute
access (escape chains), generator-based DoS (`while True: yield x`), and the
`match/case` syntax (not yet supported by branch detection).
"""
from __future__ import annotations

import ast

BLOCKED_MODULES = {
    "os", "sys", "subprocess", "requests", "urllib", "httpx", "socket",
    "sqlite3", "pickle", "importlib", "shutil", "builtins",
    "ctypes",
    "multiprocessing",
    "threading",
    "signal",
    "mmap",
    "resource",
    "gc",
    "pty",
}


BLOCKED_FUNCTIONS = {
    "eval", "exec", "open", "__import__", "getattr", "setattr", "input", "compile",
    "breakpoint",
    "vars",
    "globals",
    "locals",
    "memoryview",
    "dir",
}


# Workstream 5: extended dunder denylist. Any attribute name starting and ending
# with `__` is rejected outright by the visit_Attribute check below. This list
# is the *minimum* set; the `_DUNDER_PREFIX` test rejects the entire class.
BLOCKED_ATTRIBUTES = frozenset({
    "__globals__", "__code__", "__subclasses__", "__builtins__", "__import__",
    # Common escape chains
    "__mro__", "__bases__", "__init_subclass__", "__class__", "__dict__",
    "__getattribute__", "__getattr__", "__setattr__", "__delattr__",
    "__reduce__", "__reduce_ex__", "__getstate__", "__setstate__",
    "__getitem__", "__setitem__", "__delitem__",
    "__enter__", "__exit__", "__aenter__", "__aexit__",
    "__iter__", "__next__", "__aiter__", "__anext__",
    "__call__", "__new__", "__init__",
    "__del__", "__repr__", "__str__", "__format__",
    "__hash__", "__bool__", "__len__", "__contains__",
    "__add__", "__sub__", "__mul__", "__truediv__", "__floordiv__",
    "__mod__", "__pow__", "__neg__", "__pos__", "__abs__",
    "__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__",
})


class SandboxSecurityVisitor(ast.NodeVisitor):
    """AST visitor that accumulates blocked patterns and warnings."""

    def __init__(self):
        self.blocking: list[dict] = []
        self.warnings: list[dict] = []

    def visit_Import(self, node):
        for alias in node.names:
            base_module = alias.name.split(".")[0]
            if base_module in BLOCKED_MODULES:
                self.blocking.append({
                    "pattern": "dangerous_import",
                    "matched": f"import {alias.name}",
                })
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            base_module = node.module.split(".")[0]
            if base_module in BLOCKED_MODULES:
                self.blocking.append({
                    "pattern": "dangerous_import",
                    "matched": f"from {node.module} import ...",
                })
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            if node.func.id in BLOCKED_FUNCTIONS:
                pattern = "file_io" if node.func.id == "open" else "dangerous_builtin"
                self.blocking.append({
                    "pattern": pattern,
                    "matched": f"{node.func.id}()",
                })
            elif node.func.id == "print":
                self.warnings.append({
                    "pattern": "print_statement",
                    "matched": "print()",
                })
        self.generic_visit(node)

    def visit_Attribute(self, node):
        # Workstream 5: reject ALL dunder attribute access, not just the
        # previously hard-coded list. This closes `obj.__class__.__mro__[1].__subclasses__()`
        # style escape chains even when the attacker uses a less common dunder.
        if node.attr.startswith("__") and node.attr.endswith("__") or node.attr in BLOCKED_ATTRIBUTES:
            self.blocking.append({
                "pattern": "dangerous_attribute",
                "matched": f".{node.attr}",
            })
        self.generic_visit(node)

    def visit_Name(self, node):
        if node.id == "__builtins__":
            self.blocking.append({
                "pattern": "dangerous_builtin",
                "matched": "__builtins__",
            })
        self.generic_visit(node)

    def visit_Match(self, node):
        # Workstream 5: match/case is rejected until branch detection supports it.
        # The current `generate_tutor_checkpoints` only handles `if`, `for`, `while`,
        # and `BoolOp`; allowing match/case would produce traces that silently
        # omit the branch chips for these constructs.
        self.blocking.append({
            "pattern": "unsupported_syntax",
            "matched": "match/case statement",
        })
        self.generic_visit(node)

    def visit_While(self, node):
        # Workstream 5: reject `while True: yield ...` patterns that evade the
        # step counter. Generators are not invoked until iterated, so a generator
        # body can run forever when iterated once — even if it would otherwise
        # be bounded.
        if self._is_constant_truthy(node.test) and self._body_has_yield(node.body):
            self.blocking.append({
                "pattern": "generator_dos",
                "matched": "while <truthy>: yield ...",
            })
        self.generic_visit(node)

    @staticmethod
    def _is_constant_truthy(test: ast.AST) -> bool:
        if isinstance(test, ast.Constant):
            return bool(test.value)
        if isinstance(test, ast.NameConstant):  # py<3.8 fallback
            return bool(test.value)
        if isinstance(test, ast.Name) and test.id == "True":
            return True
        return False

    @staticmethod
    def _body_has_yield(body: list[ast.stmt]) -> bool:
        for stmt in body:
            for sub in ast.walk(stmt):
                if isinstance(sub, (ast.Yield, ast.YieldFrom)):
                    return True
        return False


def validate_code(source: str) -> tuple[bool, list[dict], list[dict]]:
    """Check user code for dangerous side effects using recursive AST parsing.

    Args:
        source: The full Python source as a string.

    Returns:
        A 3-tuple `(is_valid, blocking_effects, warnings)`:
            - `is_valid` is True if no blocking pattern was found.
            - `blocking_effects` is a list of `{pattern, matched}` dicts; empty when safe.
            - `warnings` is a list of non-blocking advisories (currently only `print()`).

    Notes:
        Syntax errors are NOT treated as blocking here — `compile()` in `runner.py`
        will catch them with line numbers. We let the compile step own syntax errors
        so the user gets the precise location.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return (True, [], [])

    visitor = SandboxSecurityVisitor()
    visitor.visit(tree)

    return (len(visitor.blocking) == 0, visitor.blocking, visitor.warnings)
