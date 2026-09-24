"""Unit tests for `app.services.fingerprint`.

These pin:
  1. The contract of `Fingerprint.compact()` / `short()` / `signature()` so
     any future tweak to the wire format shows up as a red test.
  2. The complexity-bucket classifier against the 6 registered task-battery
     snippets — B01..B06 — so a refactor of the rubric has to be a
     deliberate decision, not an accident.
  3. Edge cases (empty / syntax-error / recursion-false-positive).
  4. The SVG card generator's contract (must contain fingerprint, brand,
     and metadata) and the `code_preview` heuristics.

The signatures in `GOLDEN_SIGNATURES` are deterministic — `compute_fingerprint`
is pure Python over `code` + `steps` — so this is a stable test even if we
later refactor internals.
"""
from __future__ import annotations

import pytest

from app.services.fingerprint import (
    GREEN,
    RED,
    YELLOW,
    Fingerprint,
    code_preview,
    compute_fingerprint,
    render_fingerprint_svg,
)


# ── Sample code (the 6 task-battery items from docs/study-instruments/) ──

B01_OFF_BY_ONE = '''def sum_first_n(n):
    total = 0
    for i in range(1, n):
        total = total + i
    return total

print(sum_first_n(5))
'''

B02_MUTABLE_DEFAULT = '''def add_student(name, roster=[]):
    roster.append(name)
    return roster

class_a = add_student("Alice")
class_b = add_student("Bob")
'''

B03_SHORT_CIRCUIT = '''def get_default_name(name):
    if name or "Guest":
        return name
    return "Guest"
'''

B04_MUTATION_ITER = '''def remove_negatives(nums):
    for num in nums:
        if num < 0:
            nums.remove(num)
    return nums

data = [1, -2, 3, -4, 5]
print(remove_negatives(data))
'''

B05_VARIABLE_SHADOW = '''PI = 3.14159

def circle_area(radius):
    PI = 3
    return PI * radius ** 2
'''

B06_BARE_EXCEPT = '''def safe_divide(a, b):
    try:
        result = a / b
        return result
    except:
        return "Error"

print(safe_divide(10, 2))
print(safe_divide(10, 0))
'''

FIBONACCI = '''def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)

print(fib(10))
'''


def _steps(n: int = 8, *, has_exception: bool = False) -> list[dict]:
    """Synthesize a deterministic trace-step list for tests.

    The classifier only inspects `opcode`, `duration_ms`, and
    `exception_info`, so we don't need a full trace. Keep `n` low so the
    step-based complexity bucket falls in the green range.
    """
    out = []
    for i in range(n):
        out.append({
            "step_number": i,
            "line_number": i + 1,
            "opcode": "LINE",
            "duration_ms": 0.5,
            "exception_info": None,
            "variables": {},
            "branches_taken": {},
        })
    if has_exception:
        out[2]["exception_info"] = "ZeroDivisionError: division by zero"
    return out


# ── 1. Wire format contract ─────────────────────────────────────────────


def test_compact_includes_all_eight_components():
    """The compact string is exactly `◆B…-R…-E…-LO…-EX…-CC🟢-T…` (8 dash-separated
    fields, with the ◆ glyph welded to the branches field)."""
    fp = compute_fingerprint(B01_OFF_BY_ONE, _steps())
    assert fp.compact().startswith("◆"), f"compact must start with ◆, got {fp.compact()!r}"
    # Strip the leading ◆ then split on "-"
    body = fp.compact()[1:]
    parts = body.split("-")
    assert parts[0].startswith("B")        # branches
    assert parts[1].startswith("R")        # recursion
    assert parts[2].startswith("E")        # exception types
    assert parts[3].startswith("LO")       # loop iterations
    assert parts[4].startswith("EX")       # total steps
    assert parts[5].startswith("CC")       # complexity
    assert parts[6].startswith("T")        # duration
    assert len(parts) == 7


def test_short_is_og_card_friendly():
    """`short()` drops the EX and CC components for the OG card title line."""
    fp = compute_fingerprint(B01_OFF_BY_ONE, _steps())
    s = fp.short()
    assert s.startswith("◆")
    assert "·" in s                # separator is mid-dot
    assert "CC" not in s           # no complexity in the short form
    assert "EX" not in s           # no total steps


def test_signature_is_deterministic_short_hash():
    """Same code+steps → same signature. Different code → different signature."""
    fp1 = compute_fingerprint(B01_OFF_BY_ONE, _steps())
    fp2 = compute_fingerprint(B01_OFF_BY_ONE, _steps())
    assert fp1.signature() == fp2.signature()
    fp3 = compute_fingerprint(B04_MUTATION_ITER, _steps())
    assert fp1.signature() != fp3.signature()
    # SHA-1 prefix is exactly 10 hex chars
    assert len(fp1.signature()) == 10
    assert all(c in "0123456789abcdef" for c in fp1.signature())


def test_to_dict_round_trip():
    """`to_dict()` includes every component needed by clients."""
    fp = compute_fingerprint(B04_MUTATION_ITER, _steps())
    d = fp.to_dict()
    for key in (
        "branches",
        "recursion_depth",
        "exception_types",
        "loop_iterations",
        "total_steps",
        "conceptual_complexity",
        "total_duration_ms",
        "ast_metrics",
        "compact",
        "short",
        "signature",
    ):
        assert key in d, f"missing key {key!r} in to_dict()"


def test_compact_uses_unicode_traffic_lights():
    """The complexity slot uses 🟢 / 🟡 / 🔴 directly — no ASCII fallback."""
    fp = compute_fingerprint(B05_VARIABLE_SHADOW, _steps())
    assert fp.conceptual_complexity in (GREEN, YELLOW, RED)
    # The CC slot appears in compact() with the glyph and a trailing dash
    assert f"-CC{fp.conceptual_complexity}-" in fp.compact()


# ── 2. Classifier — golden values per task-battery snippet ──────────────


@pytest.mark.parametrize(
    "name,code,expected_branches,expected_recursion,expected_cc",
    [
        # B01: single for-loop, peak nesting 2 → score 1 → GREEN
        ("B01_off_by_one", B01_OFF_BY_ONE, 1, 0, GREEN),
        # B02: function only, no branches → score 0 → GREEN
        ("B02_mutable_default", B02_MUTABLE_DEFAULT, 0, 0, GREEN),
        # B03: 1 if + 1 short-circuit (`or` is a BoolOp with 2 values) → score 2 → GREEN
        ("B03_short_circuit", B03_SHORT_CIRCUIT, 2, 0, GREEN),
        # B04: 1 for + 1 if, peak nesting 3 → score 3 → YELLOW
        ("B04_mutation_iter", B04_MUTATION_ITER, 2, 0, YELLOW),
        # B05: just a function def → score 0 → GREEN
        ("B05_variable_shadow", B05_VARIABLE_SHADOW, 0, 0, GREEN),
        # B06: 1 try → score 1 → GREEN (only YELLOW when an exception fires)
        ("B06_bare_except_clean", B06_BARE_EXCEPT, 1, 0, GREEN),
        # fibonacci: 1 if + recursion weight 2 → score 3 → YELLOW
        ("fibonacci_recursive", FIBONACCI, 1, 1, YELLOW),
    ],
)
def test_classifier_golden_values(name, code, expected_branches, expected_recursion, expected_cc):
    """Pin the classifier's outputs against the 7 reference snippets.

    The thresholds (green/yellow/red) are rubric constants — see the module
    docstring. If you intentionally change them, update these expectations.
    """
    fp = compute_fingerprint(code, _steps(n=8))
    assert fp.branches == expected_branches, f"{name}: branches got {fp.branches}"
    assert fp.recursion_depth == expected_recursion, (
        f"{name}: recursion got {fp.recursion_depth}, expected {expected_recursion}"
    )
    assert fp.conceptual_complexity == expected_cc, (
        f"{name}: cc got {fp.conceptual_complexity}, expected {expected_cc}"
    )


def test_recursion_only_flagged_inside_callee_body():
    """The big recursion-detector fix: a top-level call to a defined function
    must NOT count as recursive. Only calls inside the function's own body."""
    # fibonacci calls itself from inside fib() — should count as recursive.
    fp_fib = compute_fingerprint(FIBONACCI, _steps(n=4))
    assert fp_fib.recursion_depth == 1

    # B01 has `def sum_first_n` + `print(sum_first_n(5))`. Top-level call.
    # Must not be flagged as recursive.
    fp_b01 = compute_fingerprint(B01_OFF_BY_ONE, _steps(n=4))
    assert fp_b01.recursion_depth == 0, (
        "Top-level `print(sum_first_n(5))` is being misread as recursion"
    )


def test_bare_except_flags_one_exception_type():
    """B06's safe_divide with one ZeroDivisionError should expose exactly
    one exception type, and the loop-iteration count is whatever the trace
    recorded."""
    fp = compute_fingerprint(B06_BARE_EXCEPT, _steps(n=8, has_exception=True))
    assert fp.exception_types == ["ZeroDivisionError"]


def test_classifier_handles_syntax_error():
    """A parse failure must not raise; it returns a zeroed fingerprint."""
    fp = compute_fingerprint("def broken(:\n    pass", _steps())
    assert fp.branches == 0
    assert fp.recursion_depth == 0
    assert fp.total_steps == 8           # step count is still honoured
    assert fp.conceptual_complexity == GREEN


def test_classifier_handles_empty_inputs():
    """Both empty code and empty (None) steps must produce a safe default.

    With empty code: AST walker sees nothing, so branches=0; classifier
    falls back to all-zeros. With valid code but None steps: AST still
    parses the code, so we get the code-derived counts but step-derived
    metrics are zero.
    """
    fp = compute_fingerprint("", [])
    assert fp.compact() == f"◆B0-R0-E0-LO0-EX0-CC{GREEN}-T<1ms"

    # Valid code, no trace steps — branches still come from the AST.
    fp = compute_fingerprint(B01_OFF_BY_ONE, None)
    assert fp.branches == 1
    assert fp.conceptual_complexity == GREEN
    assert fp.compact() == f"◆B1-R0-E0-LO0-EX0-CC{GREEN}-T<1ms"


def test_classifier_handles_no_branches_in_function():
    """A trivial `def f(): return 1` should classify as 🟢."""
    fp = compute_fingerprint("def f():\n    return 1\n", _steps(n=4))
    assert fp.branches == 0
    assert fp.conceptual_complexity == GREEN


def test_classifier_promotes_to_yellow_for_exception_branch():
    """Adding any caught exception type should bump the bucket from green to
    yellow (or higher) — exceptions are a strong 'this got tricky' signal."""
    fp_no_exc = compute_fingerprint(B06_BARE_EXCEPT, _steps(n=8, has_exception=False))
    fp_with_exc = compute_fingerprint(B06_BARE_EXCEPT, _steps(n=8, has_exception=True))
    assert fp_no_exc.conceptual_complexity == GREEN
    assert fp_with_exc.conceptual_complexity == YELLOW


def test_duration_summed_across_steps():
    """total_duration_ms is the sum of every step's duration_ms."""
    steps = _steps(n=5)  # each step has duration_ms=0.5
    fp = compute_fingerprint(B01_OFF_BY_ONE, steps)
    assert fp.total_duration_ms == pytest.approx(2.5)


def test_loop_iterations_count_iteration_opcodes():
    """Loop iterations count opcodes starting with BEFORE_FOR / BEFORE_WHILE
    / ITERATION. A trace with two loop iterations yields LO2."""
    steps = _steps(n=8)
    steps[1]["opcode"] = "BEFORE_FOR"
    steps[5]["opcode"] = "ITERATION"
    fp = compute_fingerprint(B01_OFF_BY_ONE, steps)
    assert fp.loop_iterations == 2


def test_fingerprint_dataclass_defaults_to_green():
    """A bare Fingerprint() is safe to construct without arguments."""
    fp = Fingerprint()
    assert fp.compact() == f"◆B0-R0-E0-LO0-EX0-CC{GREEN}-T<1ms"


# ── 3. SVG card contract ───────────────────────────────────────────────


def test_svg_card_contains_signature_and_brand():
    """The OG card must contain the fingerprint, the brand, and a code preview."""
    fp = compute_fingerprint(B06_BARE_EXCEPT, _steps(n=8, has_exception=True))
    svg = render_fingerprint_svg(
        fp,
        title="B06 — bare except",
        code_preview=code_preview(B06_BARE_EXCEPT),
    )
    # It's bytes, not str
    assert isinstance(svg, bytes)
    assert svg.startswith(b"<svg")
    assert b"COGNITRACE" in svg.upper()
    # The signature short form must be in the card
    assert fp.short().encode("utf-8") in svg


def test_svg_card_handles_empty_code_preview():
    """Empty code preview must not break the renderer."""
    fp = compute_fingerprint(B01_OFF_BY_ONE, _steps(n=4))
    svg = render_fingerprint_svg(fp, title="empty", code_preview="")
    assert b"<svg" in svg
    # The metric table still renders even with no code preview
    assert b"METRICS" in svg


def test_svg_card_uses_dark_background_and_metric_table():
    """The OG card has the dark CogniTrace gradient and the 8-row metrics table."""
    fp = compute_fingerprint(B06_BARE_EXCEPT, _steps(n=8, has_exception=True))
    svg = render_fingerprint_svg(fp, title="x", code_preview="")
    assert b"<linearGradient" in svg
    assert b"METRICS" in svg
    # The 8 expected metric rows
    for label in (b"Branches", b"Recursion", b"Exceptions", b"Loop iters",
                  b"Steps", b"Duration", b"Complexity", b"Signature"):
        assert label in svg, f"metric label {label!r} missing from SVG card"


# ── 4. code_preview ─────────────────────────────────────────────────────


def test_code_preview_drops_comment_runs():
    """`code_preview` keeps one comment for context and skips the rest."""
    code = "# header comment\n# redundant\nx = 1\ny = 2\n# trailing\n"
    preview = code_preview(code, max_lines=4)
    lines = preview.splitlines()
    assert lines[0].startswith("# header")
    assert "redundant" not in preview
    assert "trailing" not in preview
    assert "x = 1" in preview
    assert "y = 2" in preview


def test_code_preview_collapses_blank_lines():
    """Multiple consecutive blank lines collapse to a single blank."""
    code = "x = 1\n\n\n\n\ny = 2\n"
    preview = code_preview(code, max_lines=4)
    assert preview.count("\n\n") == 1


def test_code_preview_respects_max_lines():
    """`max_lines=2` keeps at most 2 code lines."""
    code = "a = 1\nb = 2\nc = 3\nd = 4\n"
    preview = code_preview(code, max_lines=2)
    assert preview.count("\n") + 1 == 2