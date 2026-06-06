"""Side-effect detection for user code validation using AST parsing."""
import ast

BLOCKED_MODULES = {
    "os", "sys", "subprocess", "requests", "urllib", "httpx", "socket", 
    "sqlite3", "pickle", "importlib", "shutil", "builtins"
}

BLOCKED_FUNCTIONS = {
    "eval", "exec", "open", "__import__", "getattr", "setattr", "input", "compile"
}

BLOCKED_ATTRIBUTES = {
    "__globals__", "__code__", "__subclasses__", "__builtins__", "__import__"
}

class SandboxSecurityVisitor(ast.NodeVisitor):
    def __init__(self):
        self.blocking = []
        self.warnings = []

    def visit_Import(self, node):
        for alias in node.names:
            base_module = alias.name.split('.')[0]
            if base_module in BLOCKED_MODULES:
                self.blocking.append({
                    "pattern": "dangerous_import",
                    "matched": f"import {alias.name}"
                })
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            base_module = node.module.split('.')[0]
            if base_module in BLOCKED_MODULES:
                self.blocking.append({
                    "pattern": "dangerous_import",
                    "matched": f"from {node.module} import ..."
                })
        self.generic_visit(node)

    def visit_Call(self, node):
        # Detect eval(), exec(), open(), getattr(), setattr(), input(), __import__(), compile()
        if isinstance(node.func, ast.Name):
            if node.func.id in BLOCKED_FUNCTIONS:
                pattern = "file_io" if node.func.id == "open" else "dangerous_builtin"
                self.blocking.append({
                    "pattern": pattern,
                    "matched": f"{node.func.id}()"
                })
            # Detect print() statements (warning only)
            elif node.func.id == "print":
                self.warnings.append({
                    "pattern": "print_statement",
                    "matched": "print()"
                })
        self.generic_visit(node)

    def visit_Attribute(self, node):
        # Detect access to __globals__, __subclasses__, __code__, etc.
        if node.attr in BLOCKED_ATTRIBUTES:
            self.blocking.append({
                "pattern": "dangerous_attribute",
                "matched": f".{node.attr}"
            })
        self.generic_visit(node)

    def visit_Name(self, node):
        # Detect reference to __builtins__
        if node.id == "__builtins__":
            self.blocking.append({
                "pattern": "dangerous_builtin",
                "matched": "__builtins__"
            })
        self.generic_visit(node)


def validate_code(source: str) -> tuple[bool, list[dict], list[dict]]:
    """
    Check user code for dangerous side effects using recursive AST parsing.

    Returns: (is_valid, blocking_effects, warnings)
    - is_valid: True if code is safe to execute
    - blocking_effects: [] if safe, list of matched dangerous patterns if not
    - warnings: list of warnings (print() is warning only, not blocking)
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Let the compiler/runner handle syntax errors with line numbers
        return (True, [], [])

    visitor = SandboxSecurityVisitor()
    visitor.visit(tree)

    return (len(visitor.blocking) == 0, visitor.blocking, visitor.warnings)
