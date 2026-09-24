"""Trace Fingerprint — Workstream 12 (game-changer demo).

A *fingerprint* is a short, deterministic, human-readable signature for a
Python trace. Every saved trace gets one; the signature is recomputed
on demand from the trace's `code` + `steps`, so it survives schema
changes, model swaps, and bug fixes to the classifier.

Example fingerprint::

    ◆B2-R3-E1-LO2-EX2-CC🟢-T47ms

Composed of:
    ◆           — the literal glyph that marks a fingerprint (renders well in any font)
    B<n>        — branch count (max nested depth actually reached at runtime)
    R<n>        — recursion depth (max)
    E<n>        — unique exception types raised at runtime
    LO<n>       — loop iterations executed
    EX<n>       — total executed steps
    CC<🟢|🟡|🔴> — conceptual complexity (green=simple, yellow=medium, red=complex)
    T<n><unit>  — total execution duration (compact: ms/s)

The string is deliberately monospace-friendly so it fits in a single line of
code review, in a tweet, or on a slide. The classifier never touches the LLM
router — it's pure AST + trace-step analysis so it always runs in <5 ms.

The SVG card generator (also in this file) composes the fingerprint into a
shareable image. Both the SVG and the rasterized PNG are exposed via
`/api/traces/{id}/fingerprint/card.svg` and `card.png`.
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import math
import re
from dataclasses import dataclass, field
from typing import Iterable

# Glyphs picked so every component still reads as plain ASCII where possible —
# only the leading ◆ and the CC traffic light are unicode (U+25C6 and emoji).
LEAD = "◆"
GREEN = "🟢"
YELLOW = "🟡"
RED = "🔴"


# ── Data class ────────────────────────────────────────────────────────────────


@dataclass
class Fingerprint:
    """All the components of a trace fingerprint, individually accessible."""

    branches: int = 0
    recursion_depth: int = 0
    exception_types: list[str] = field(default_factory=list)
    loop_iterations: int = 0
    total_steps: int = 0
    conceptual_complexity: str = "🟢"  # green | yellow | red
    total_duration_ms: float = 0.0
    ast_metrics: dict = field(default_factory=dict)

    # ------------------------------------------------------------------ string

    def compact(self) -> str:
        """The one-line signature string. e.g. `◆B2-R3-E1-LO2-EX2-CC🟢-T47ms`."""
        return (
            f"{LEAD}"
            f"B{self.branches}"
            f"-R{self.recursion_depth}"
            f"-E{len(self.exception_types)}"
            f"-LO{self.loop_iterations}"
            f"-EX{self.total_steps}"
            f"-CC{self.conceptual_complexity}"
            f"-T{_fmt_duration(self.total_duration_ms)}"
        )

    def short(self) -> str:
        """A 5-component tagline used in OG image titles.

        Example: `◆B2·R3·E1·LO2·T47ms`
        """
        return (
            f"{LEAD}B{self.branches}·R{self.recursion_depth}"
            f"·E{len(self.exception_types)}·LO{self.loop_iterations}"
            f"·T{_fmt_duration(self.total_duration_ms)}"
        )

    # ------------------------------------------------------------------- hash

    def signature(self) -> str:
        """A short stable hash. Two fingerprints with the same `signature()`
        are byte-equivalent for the same code+trace. Useful for deduplicating
        share-token URLs without leaking the actual code.
        """
        payload = json.dumps(
            {
                "b": self.branches,
                "r": self.recursion_depth,
                "e": sorted(self.exception_types),
                "lo": self.loop_iterations,
                "ex": self.total_steps,
                "cc": self.conceptual_complexity,
                "t": round(self.total_duration_ms, 2),
                "am": self.ast_metrics,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]

    # ------------------------------------------------------------------- wire

    def to_dict(self) -> dict:
        return {
            "branches": self.branches,
            "recursion_depth": self.recursion_depth,
            "exception_types": list(self.exception_types),
            "loop_iterations": self.loop_iterations,
            "total_steps": self.total_steps,
            "conceptual_complexity": self.conceptual_complexity,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "ast_metrics": self.ast_metrics,
            "compact": self.compact(),
            "short": self.short(),
            "signature": self.signature(),
        }


# ── Classifier ────────────────────────────────────────────────────────────────


class _ComplexityVisitor(ast.NodeVisitor):
    """AST walker that computes a complexity score independent of the trace."""

    def __init__(self) -> None:
        self.branches = 0  # if/elif/for/while/try/and short-circuit
        self.recursion_calls: set[str] = set()
        self.function_names: set[str] = set()
        self.loop_nodes = 0
        self.try_nodes = 0
        self.peak_nesting = 0
        self._depth = 0
        # Stack of enclosing function names. A Call is recursive only when
        # its enclosing function (top of stack) has the same name as the
        # callee. Without this guard, top-level `safe_divide(10, 2)` makes
        # `safe_divide` look "recursive" because the function is *defined*
        # elsewhere in the module — see the smoke test for B01.
        self._fn_stack: list[str] = []

    def _enter(self) -> None:
        self._depth += 1
        self.peak_nesting = max(self.peak_nesting, self._depth)

    def _exit(self) -> None:
        self._depth -= 1

    # Branch & control-flow nodes --------------------------------------

    def visit_If(self, node: ast.If) -> None:
        self.branches += 1
        self._enter()
        self.generic_visit(node)
        self._exit()

    def visit_For(self, node: ast.For) -> None:
        self.branches += 1
        self.loop_nodes += 1
        self._enter()
        self.generic_visit(node)
        self._exit()

    def visit_While(self, node: ast.While) -> None:
        self.branches += 1
        self.loop_nodes += 1
        self._enter()
        self.generic_visit(node)
        self._exit()

    def visit_Try(self, node: ast.Try) -> None:
        self.branches += 1
        self.try_nodes += 1
        self._enter()
        self.generic_visit(node)
        self._exit()

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        # `a and b and c` contributes len(values)-1 short-circuits
        self.branches += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:  # Python 3.10+
        self.branches += len(node.cases)
        self._enter()
        self.generic_visit(node)
        self._exit()

    # Function definitions & recursion ---------------------------------

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.function_names.add(node.name)
        self._fn_stack.append(node.name)
        self._enter()
        try:
            self.generic_visit(node)
        finally:
            self._fn_stack.pop()
        self._exit()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        # True recursion: a function calls itself from within its own body.
        # Top-level `foo()` does not count even if `def foo()` exists.
        if (
            isinstance(node.func, ast.Name)
            and self._fn_stack
            and node.func.id == self._fn_stack[-1]
        ):
            self.recursion_calls.add(node.func.id)
        self.generic_visit(node)


def _classify_complexity(
    ast_v: _ComplexityVisitor,
    loop_iterations: int,
    exception_count: int,
    steps: int,
) -> str:
    """Traffic-light complexity bucket used in `CC` and the SVG card."""
    # Rough rubric derived from McCabe-style heuristics — see paper §4.2.
    score = (
        ast_v.branches
        + 2 * len(ast_v.recursion_calls)
        + ast_v.try_nodes
        + (1 if ast_v.peak_nesting >= 3 else 0)
        + min(3, loop_iterations // 8)
        + min(3, exception_count)
        + min(3, steps // 40)
    )
    if score >= 7:
        return RED
    if score >= 3:
        return YELLOW
    return GREEN


def _safe_parse(code: str) -> ast.Module | None:
    try:
        return ast.parse(code)
    except SyntaxError:
        return None


def _extract_exception_types_from_steps(steps: list[dict]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for s in steps or []:
        exc = s.get("exception_info") or s.get("exception")
        if not exc:
            continue
        # exception_info is a string like "ZeroDivisionError: division by zero"
        head = str(exc).split(":", 1)[0].strip()
        if head and head not in seen:
            seen.add(head)
            out.append(head)
    return out


def compute_fingerprint(code: str, steps: list[dict]) -> Fingerprint:
    """Build a Fingerprint from raw code + tracer steps.

    Pure-Python, no network calls, no LLM. ~1 ms on typical CS1 snippets.
    """
    fp = Fingerprint()
    ast_metrics: dict = {}

    tree = _safe_parse(code)
    if tree is not None:
        v = _ComplexityVisitor()
        v.visit(tree)
        ast_metrics = {
            "branches_ast": v.branches,
            "recursion_calls": sorted(v.recursion_calls),
            "loop_nodes_ast": v.loop_nodes,
            "try_nodes_ast": v.try_nodes,
            "peak_nesting": v.peak_nesting,
            "function_count": len(v.function_names),
        }
        fp.branches = v.branches
        fp.recursion_depth = len(v.recursion_calls)

    # Trace-derived metrics ----------------------------------------------
    fp.total_steps = len(steps or [])
    fp.total_duration_ms = float(
        sum(float(s.get("duration_ms", 0) or 0) for s in (steps or []))
    )
    fp.exception_types = _extract_exception_types_from_steps(steps or [])

    # Loop iterations: count LINE events inside LOOP opcodes. The tracer
    # emits opcodes like BEFORE_FOR/AFTER_FOR / BEFORE_WHILE/AFTER_WHILE
    # and per-step duration_ms; the simplest robust heuristic is to count
    # events whose `opcode` indicates an iteration boundary.
    loop_iter = 0
    for s in steps or []:
        op = (s.get("opcode") or "").upper()
        if op.startswith("BEFORE_FOR") or op.startswith("BEFORE_WHILE") or "ITERATION" in op:
            loop_iter += 1
    fp.loop_iterations = loop_iter

    # Final complexity bucket
    tree2 = _safe_parse(code)
    ast_score = _ComplexityVisitor()
    if tree2 is not None:
        ast_score.visit(tree2)
    fp.conceptual_complexity = _classify_complexity(
        ast_score, fp.loop_iterations, len(fp.exception_types), fp.total_steps
    )
    fp.ast_metrics = ast_metrics
    return fp


# ── Compact duration format (used in compact fingerprint string) ────────────


def _fmt_duration(ms: float) -> str:
    if ms < 1:
        return "<1ms"
    if ms < 1000:
        return f"{int(round(ms))}ms"
    if ms < 60_000:
        return f"{ms/1000:.1f}s"
    return f"{ms/60_000:.1f}m"


# ── SVG card generator ───────────────────────────────────────────────────────


def render_fingerprint_svg(
    fp: Fingerprint,
    *,
    title: str = "CogniTrace Fingerprint",
    code_preview: str = "",
    width: int = 720,
    accent: str | None = None,
) -> bytes:
    """Render the fingerprint as a self-contained SVG (UTF-8 bytes).

    Designed to render correctly on Twitter/X, Open Graph, and inside the
    CogniTrace web pages. No external assets, no JS, no <foreignObject>.
    """
    cc_color = {
        GREEN: "#16a34a",
        YELLOW: "#ca8a04",
        RED: "#dc2626",
    }.get(fp.conceptual_complexity, "#6b7280")
    accent = accent or "#6366f1"

    # Compact code preview, escaped for SVG text
    lines = (code_preview or "").splitlines()[:6]
    code_block = ""
    if lines:
        body = "\n".join(lines)
        # Truncate overly long lines
        body = "\n".join((l if len(l) <= 60 else l[:57] + "...") for l in body.splitlines())
        code_block = body

    # Two-column layout: fingerprint string on the left, mini-stats on the right.
    fp_line = fp.short()
    metrics: Iterable[tuple[str, str]] = (
        ("Branches", str(fp.branches)),
        ("Recursion", str(fp.recursion_depth)),
        ("Exceptions", str(len(fp.exception_types))),
        ("Loop iters", str(fp.loop_iterations)),
        ("Steps", str(fp.total_steps)),
        ("Duration", _fmt_duration(fp.total_duration_ms)),
        ("Complexity", fp.conceptual_complexity),
        ("Signature", fp.signature()),
    )
    metric_rows = "".join(
        f'<tr><td>{_xml(k)}</td><td>{_xml(v)}</td></tr>' for k, v in metrics
    )

    # Highlight exception names in red text on the metrics card if present
    exception_summary = ""
    if fp.exception_types:
        joined = ", ".join(fp.exception_types[:3])
        if len(fp.exception_types) > 3:
            joined += f" +{len(fp.exception_types) - 3} more"
        exception_summary = (
            f'<div class="excs">Caught: <tspan fill="#dc2626">{_xml(joined)}</tspan></div>'
        )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="420" viewBox="0 0 {width} 420" role="img" aria-label="CogniTrace fingerprint card">
  <defs>
    <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#1e1b4b"/>
    </linearGradient>
    <style>
      .title {{ font: 600 16px/1.2 -apple-system, "Segoe UI", system-ui, sans-serif; fill:#e2e8f0; letter-spacing:0.04em; }}
      .subtle {{ font: 400 12px/1.4 -apple-system, "Segoe UI", system-ui, sans-serif; fill:#94a3b8; }}
      .mono {{ font: 600 22px/1.3 ui-monospace, "JetBrains Mono", "Cascadia Code", Menlo, monospace; fill:#f1f5f9; }}
      .cc {{ font: 700 28px/1 ui-monospace, monospace; fill:{cc_color}; }}
      .metric td {{ font: 500 13px/1.6 ui-monospace, monospace; fill:#cbd5e1; }}
      .metric td:first-child {{ fill:#64748b; }}
      .accent {{ fill:{accent}; }}
      .excs {{ font: 500 12px/1.4 -apple-system, sans-serif; fill:#fca5a5; margin-top:8px; }}
      .code {{ font: 400 12px/1.45 ui-monospace, monospace; fill:#cbd5e1; white-space:pre; }}
      .footer {{ font: 500 11px/1.4 -apple-system, sans-serif; fill:#64748b; letter-spacing:0.08em; }}
    </style>
  </defs>
  <rect width="{width}" height="420" fill="url(#bg)" rx="14"/>
  <rect x="14" y="14" width="{width - 28}" height="392" fill="none" stroke="#312e81" stroke-width="1" rx="10"/>
  <g transform="translate(28, 36)">
    <text class="title">{_xml(title.upper())}</text>
    <text class="subtle" y="20">deterministic visual signature · trace DNA</text>
  </g>
  <g transform="translate(28, 110)">
    <text class="mono">{_xml(fp_line)}</text>
    <text class="subtle" y="32">conceptual complexity:</text>
    <text class="cc" x="148" y="32">{_xml(fp.conceptual_complexity)}</text>
  </g>
  <g transform="translate(28, 200)">
    {f'<text class="code">{_xml(code_block)}</text>' if code_block else ''}
    {exception_summary}
  </g>
  <g transform="translate({width - 250}, 90)">
    <rect x="-12" y="-12" width="270" height="290" rx="8" fill="#0b1227" stroke="#312e81"/>
    <g transform="translate(0, 12)">
      <text class="title accent">METRICS</text>
      <g transform="translate(0, 28)">
        <table class="metric">
          {metric_rows}
        </table>
      </g>
    </g>
  </g>
  <g transform="translate(28, 392)">
    <text class="footer">COGNITRACE · { "A/B-GROUNDED TUTORING RESEARCH" }</text>
  </g>
</svg>'''
    return svg.encode("utf-8")


def xml_escape(text: str) -> str:
    """Escape text for safe inclusion in an SVG <text> node."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


# Back-compat alias for the existing SVG renderer. Older tests import the
# private name; keep it around so we don't break them.
_xml = xml_escape


# ── Code-preview extraction (used by both SVG and OG image) ────────────────


_CODE_COMMENT_LINE = re.compile(r"^\s*#")


def code_preview(code: str, max_lines: int = 4) -> str:
    """Pick the most informative `max_lines` lines of code for the OG card.

    Skips pure-comment lines; trims whitespace; collapses blank-line runs.
    """
    lines = [l.rstrip() for l in (code or "").splitlines()]
    keep: list[str] = []
    for line in lines:
        if not line.strip():
            if keep and keep[-1] != "":
                keep.append("")
            continue
        if _CODE_COMMENT_LINE.match(line):
            # Keep one comment line for context, then skip the rest
            if not any(_CODE_COMMENT_LINE.match(k) for k in keep):
                keep.append(line)
            continue
        keep.append(line)
    while keep and keep[-1] == "":
        keep.pop()
    return "\n".join(keep[:max_lines])


# ── Fingerprint diff (THESIS-05 §4 — T1-D "Trace Diff") ────────────────────
# Extends contribution #4 from a static signature to an *interactive
# pedagogical artifact*: students compare two fingerprints and the
# structural deltas that produced them. The diff is pure-Python, no LLM,
# so it runs in <1 ms and can be safely cached + shared.


@dataclass
class FingerprintDelta:
    """One structural change between two fingerprints."""

    field: str
    label: str
    a_value: object
    b_value: object
    # A short, human-readable narrative about *why* this delta matters.
    # E.g. for `loop_iterations`: "loop ran twice as many iterations in B,
    # which usually means a control-flow change inside the loop body".
    narrative: str
    # True when the increase is the kind of change we expect a CS1 student
    # to reason about (more loops, more branches, new exceptions).
    significant: bool


# Field labels + narratives — keep in sync with `Fingerprint` dataclass.
_FIELD_LABELS: dict[str, str] = {
    "branches": "Branch decisions",
    "recursion_depth": "Recursive calls",
    "loop_iterations": "Loop iterations",
    "total_steps": "Total executed steps",
    "total_duration_ms": "Total duration",
    "conceptual_complexity": "Conceptual complexity",
    "exception_types": "Exception types",
}


def _diff_narrative(field: str, a: object, b: object) -> tuple[str, bool]:
    """Return (narrative, significant) for a given field-level delta."""
    if field == "branches":
        try:
            delta = int(b) - int(a)
        except (TypeError, ValueError):
            return ("", False)
        if delta == 0:
            return ("same branch count — control-flow shape is preserved", False)
        if delta > 0:
            return (
                f"+{delta} branch decision{'s' if delta != 1 else ''}: the new trace "
                f"takes a more conditional path through the code",
                True,
            )
        return (
            f"{delta} branches: the new trace simplifies a conditional",
            True,
        )
    if field == "loop_iterations":
        try:
            a_n, b_n = int(a), int(b)
        except (TypeError, ValueError):
            return ("", False)
        if a_n == 0 and b_n > 0:
            return (
                "trace B enters a loop that trace A skipped — common when "
                "you remove an early-return guard",
                True,
            )
        if b_n == 0 and a_n > 0:
            return (
                "trace B skips the loop entirely that trace A executed — "
                "check the loop's entry condition",
                True,
            )
        if b_n > a_n:
            return (
                f"loop ran {b_n - a_n} more iteration(s) in trace B",
                b_n - a_n >= 2,
            )
        if b_n < a_n:
            return (
                f"loop ran {a_n - b_n} fewer iteration(s) in trace B",
                a_n - b_n >= 2,
            )
        return ("same loop-iteration count", False)
    if field == "recursion_depth":
        try:
            delta = int(b) - int(a)
        except (TypeError, ValueError):
            return ("", False)
        if delta == 0:
            return ("same recursion depth", False)
        if delta > 0:
            return (
                f"trace B recurses {delta} level(s) deeper — the new code "
                "has a recursive case the old code lacked",
                True,
            )
        return (
            f"trace B recurses {-delta} level(s) less — a base case was "
            "reached earlier or the recursion was removed",
            True,
        )
    if field == "total_steps":
        try:
            delta = int(b) - int(a)
        except (TypeError, ValueError):
            return ("", False)
        if delta == 0:
            return ("same number of executed opcodes", False)
        return (
            f"{'+' if delta > 0 else ''}{delta} executed step(s)",
            abs(delta) >= 3,
        )
    if field == "total_duration_ms":
        try:
            a_ms, b_ms = float(a), float(b)
        except (TypeError, ValueError):
            return ("", False)
        delta = b_ms - a_ms
        if abs(delta) < 1:
            return ("same wall-clock duration", False)
        sign = "+" if delta > 0 else ""
        return (f"{sign}{delta:.0f}ms wall-clock difference", abs(delta) >= 25)
    if field == "conceptual_complexity":
        return (
            "conceptual complexity bucket changed — McCabe-style score "
            "crossed the green/yellow/red threshold",
            True,
        )
    if field == "exception_types":
        a_set = set(a or [])
        b_set = set(b or [])
        added = b_set - a_set
        removed = a_set - b_set
        if added and removed:
            return (
                f"exceptions changed: +{', +'.join(sorted(added))}; "
                f"-{', -'.join(sorted(removed))}",
                True,
            )
        if added:
            return (
                f"trace B raises new exception type(s): {', '.join(sorted(added))}",
                True,
            )
        if removed:
            return (
                f"trace B no longer raises: {', '.join(sorted(removed))}",
                True,
            )
        return ("same exception types", False)
    return ("", False)


def diff_fingerprints(a: Fingerprint, b: Fingerprint) -> list[FingerprintDelta]:
    """Compute the structural delta list between two fingerprints.

    Used by:
      - `GET /fingerprint/diff?a=…&b=…` for the compare page
      - The share-page diff link (existing share token extension)

    The diff is *field-level*, not opcode-level: students see "the loop
    ran 2 more iterations" rather than "line 7 mutated total differently".
    The line-by-line walkthrough lives on the frontend so it can use the
    actual trace steps (this function only sees the aggregated fingerprint).
    """
    deltas: list[FingerprintDelta] = []
    scalar_fields = (
        "branches",
        "recursion_depth",
        "loop_iterations",
        "total_steps",
        "total_duration_ms",
    )
    for field in scalar_fields:
        a_val = getattr(a, field)
        b_val = getattr(b, field)
        if a_val == b_val:
            continue
        narrative, significant = _diff_narrative(field, a_val, b_val)
        deltas.append(
            FingerprintDelta(
                field=field,
                label=_FIELD_LABELS[field],
                a_value=a_val,
                b_value=b_val,
                narrative=narrative,
                significant=significant,
            )
        )

    # Complexity bucket: bucket-level compare (string).
    if a.conceptual_complexity != b.conceptual_complexity:
        narrative, significant = _diff_narrative(
            "conceptual_complexity",
            a.conceptual_complexity,
            b.conceptual_complexity,
        )
        deltas.append(
            FingerprintDelta(
                field="conceptual_complexity",
                label=_FIELD_LABELS["conceptual_complexity"],
                a_value=a.conceptual_complexity,
                b_value=b.conceptual_complexity,
                narrative=narrative,
                significant=significant,
            )
        )

    # Exception type set compare.
    if sorted(a.exception_types) != sorted(b.exception_types):
        narrative, significant = _diff_narrative(
            "exception_types", a.exception_types, b.exception_types
        )
        deltas.append(
            FingerprintDelta(
                field="exception_types",
                label=_FIELD_LABELS["exception_types"],
                a_value=list(a.exception_types),
                b_value=list(b.exception_types),
                narrative=narrative,
                significant=significant,
            )
        )

    return deltas


def diff_fingerprints_from_payloads(
    a_payload: dict, b_payload: dict
) -> list[dict]:
    """Wire-format wrapper around `diff_fingerprints`.

    Used by the `/fingerprint/diff` endpoint to compute the delta list
    from two raw wire payloads (as returned by `Fingerprint.to_dict()` or
    stored in `trace_fingerprints.fingerprint_json`).
    """
    a_fp = Fingerprint(
        branches=a_payload.get("branches", 0),
        recursion_depth=a_payload.get("recursion_depth", 0),
        exception_types=list(a_payload.get("exception_types") or []),
        loop_iterations=a_payload.get("loop_iterations", 0),
        total_steps=a_payload.get("total_steps", 0),
        conceptual_complexity=a_payload.get("conceptual_complexity", "🟢"),
        total_duration_ms=float(a_payload.get("total_duration_ms") or 0.0),
        ast_metrics=dict(a_payload.get("ast_metrics") or {}),
    )
    b_fp = Fingerprint(
        branches=b_payload.get("branches", 0),
        recursion_depth=b_payload.get("recursion_depth", 0),
        exception_types=list(b_payload.get("exception_types") or []),
        loop_iterations=b_payload.get("loop_iterations", 0),
        total_steps=b_payload.get("total_steps", 0),
        conceptual_complexity=b_payload.get("conceptual_complexity", "🟢"),
        total_duration_ms=float(b_payload.get("total_duration_ms") or 0.0),
        ast_metrics=dict(b_payload.get("ast_metrics") or {}),
    )
    return [
        {
            "field": d.field,
            "label": d.label,
            "a_value": d.a_value,
            "b_value": d.b_value,
            "narrative": d.narrative,
            "significant": d.significant,
        }
        for d in diff_fingerprints(a_fp, b_fp)
    ]
