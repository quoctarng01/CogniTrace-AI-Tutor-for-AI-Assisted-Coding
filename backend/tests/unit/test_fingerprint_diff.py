"""Unit tests for `diff_fingerprints` (T1-D).

Pins the side-by-side diff contract:

  * `identical` is True when all fields agree
  * `significant: True` is reserved for meaningful differences
  * `narrative` is a human-readable explanation per field
  * `diff_fingerprints_from_payloads` round-trips the wire format
"""
from __future__ import annotations

from app.services.fingerprint import (
    Fingerprint,
    compute_fingerprint,
    diff_fingerprints,
    diff_fingerprints_from_payloads,
)


SAMPLE_CODE_A = """\
def fibonacci(n):
    result = []
    a, b = 0, 1
    for i in range(n):
        result.append(a)
        a, b = b, a + b
    return result

print(fibonacci(5))
"""

SAMPLE_CODE_B = """\
def fibonacci(n):
    if n <= 0:
        return []
    result = []
    a, b = 0, 1
    for i in range(n):
        result.append(a)
        a, b = b, a + b
    return result

def helper(x):
    return x + 1

print(fibonacci(5))
"""


def _fp(code: str) -> Fingerprint:
    """Compute a Fingerprint from raw code (steps are inferred)."""
    return compute_fingerprint(code=code, steps=[])


# ── Identical case ─────────────────────────────────────────────────


def test_diff_identical_yields_empty_deltas():
    a = _fp(SAMPLE_CODE_A)
    b = _fp(SAMPLE_CODE_A)
    deltas = diff_fingerprints(a, b)
    assert deltas == []


# ── Branch count change ───────────────────────────────────────────


def test_diff_flags_branch_count_change():
    a = _fp(SAMPLE_CODE_A)
    b = _fp(SAMPLE_CODE_B)
    deltas = diff_fingerprints(a, b)
    branch_delta = next((d for d in deltas if d.field == "branches"), None)
    assert branch_delta is not None
    assert branch_delta.a_value != branch_delta.b_value
    # Extra defensive check from `if` → +1 branch
    assert branch_delta.b_value > branch_delta.a_value


def test_diff_marks_significant_differences():
    a = _fp(SAMPLE_CODE_A)
    b = _fp(SAMPLE_CODE_B)
    deltas = diff_fingerprints(a, b)
    # Adding a function + an if should produce multiple deltas
    assert len(deltas) > 0
    # At least one should be marked significant
    significant = [d for d in deltas if d.significant]
    assert len(significant) >= 1


def test_diff_narrative_is_human_readable():
    a = _fp(SAMPLE_CODE_A)
    b = _fp(SAMPLE_CODE_B)
    deltas = diff_fingerprints(a, b)
    assert all(d.narrative for d in deltas), "all deltas must have a narrative"
    # Narratives should mention either "trace A", "trace B", or have a
    # numeric delta phrasing like "loop ran N more iteration(s)".
    assert any(
        "trace A" in d.narrative.lower()
        or "trace B" in d.narrative.lower()
        or "more iteration" in d.narrative.lower()
        or "branch" in d.narrative.lower()
        for d in deltas
    )


# ── Wire-format round-trip ────────────────────────────────────────


def test_diff_fingerprints_from_payloads_round_trips():
    a = _fp(SAMPLE_CODE_A)
    b = _fp(SAMPLE_CODE_B)
    payload_a = a.to_dict()
    payload_b = b.to_dict()
    wire_deltas = diff_fingerprints_from_payloads(payload_a, payload_b)
    assert isinstance(wire_deltas, list)
    if wire_deltas:
        first = wire_deltas[0]
        assert set(first.keys()) >= {
            "field",
            "label",
            "a_value",
            "b_value",
            "narrative",
            "significant",
        }


def test_diff_fingerprints_from_payloads_identical_is_empty():
    a = _fp(SAMPLE_CODE_A)
    payload = a.to_dict()
    wire_deltas = diff_fingerprints_from_payloads(payload, payload)
    assert wire_deltas == []
