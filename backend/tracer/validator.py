"""Side-effect detection for user code validation."""
import re

SIDE_EFFECT_PATTERNS = [
    (r"\bimport\s+(os|sys|subprocess|requests|urllib|httpx|socket|sqlite3|pickle)", "dangerous_import"),
    (r"\bopen\s*\(", "file_io"),
    (r"\brequests\.", "http_requests"),
    (r"\bos\.", "os_module"),
    (r"\bsubprocess\.", "subprocess_module"),
    (r"\beval\s*\(", "eval_usage"),
    (r"\bexec\s*\(", "exec_usage"),
    (r"\b__import__\s*\(", "dynamic_import"),
    (r"\bgetattr\s*\(", "getattr_usage"),
    (r"\bsetattr\s*\(", "setattr_usage"),
    (r"\binput\s*\(", "input_usage"),
]

WARNING_PATTERNS = [
    (r"\bprint\s*\(", "print_statement"),
]


def validate_code(source: str) -> tuple[bool, list[dict], list[dict]]:
    """
    Check user code for dangerous side effects.

    Returns: (is_valid, blocking_effects, warnings)
    - is_valid: True if code is safe to execute
    - blocking_effects: [] if safe, list of matched dangerous patterns if not
    - warnings: list of warnings (print() is warning only, not blocking)
    """
    blocking = []
    warnings = []

    for pattern, name in SIDE_EFFECT_PATTERNS:
        match = re.search(pattern, source)
        if match:
            blocking.append({"pattern": name, "matched": match.group()})

    for pattern, name in WARNING_PATTERNS:
        match = re.search(pattern, source)
        if match:
            warnings.append({"pattern": name, "matched": match.group()})

    return (len(blocking) == 0, blocking, warnings)
