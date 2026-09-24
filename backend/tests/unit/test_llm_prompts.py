"""Unit tests for the prompt templates in `app.services.llm_prompts`.

Workstream 8 — lock in the contract of the extracted prompts module:

1. Each prompt is a non-empty string (no silent regression to `""`).
2. Each USER_*_TEMPLATE has the placeholder keys it claims to have.
3. The SYSTEM_EXPLAIN does not leak runtime code into the system prompt —
   the system prompt is fixed instructions only.
4. The FALLBACK_* dicts are stable (no surprise keys disappearing).

If you rename a prompt or change its placeholders, update the corresponding
constant at the top of this file first — the tests will fail loudly.
"""
import re

import pytest

from app.services import llm_prompts as prompts


# Matches an unrendered str.format() placeholder like {foo} or {foo[bar]} but
# not escaped braces or JSON. A real placeholder is `{identifier}` and is
# surrounded by non-brace context.
PLACEHOLDER_RE = re.compile(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}")


# Stable contract: (constant_name, expected_placeholders).
# If a prompt loses a placeholder, the format() call in the router will
# raise KeyError — but only at request time. Failing the test catches it
# at unit-test time.
EXPECTED_USER_PLACEHOLDERS = {
    "USER_EXPLAIN_TEMPLATE": ("code", "line_number", "line_content", "locals_json"),
    "USER_GRADE_EXPLANATION_TEMPLATE": ("code", "steps_json", "user_answer"),
    "USER_MISCONCEPTION_TEMPLATE": (
        "code",
        "lineno",
        "checkpoint_type",
        "variable_name",
        "correct_value",
        "user_prediction",
    ),
    "USER_REPAIR_GENERATE_TEMPLATE": ("original_code", "misconception_tag"),
    "USER_GRADE_REPAIR_TEMPLATE": ("original_code", "misconception_tag", "user_fix"),
}


def test_all_prompts_are_non_empty_strings():
    """Every prompt constant must be a non-empty string. Catches accidental empties."""
    for name in dir(prompts):
        value = getattr(prompts, name)
        if name.startswith("_"):
            continue
        if isinstance(value, str):
            assert value.strip(), f"Prompt {name} is empty/whitespace-only"
        elif isinstance(value, dict):
            assert value, f"Fallback dict {name} is empty"


def test_user_templates_have_expected_placeholders():
    """Pin the placeholder contract so router.format() never raises KeyError silently."""
    for name, expected in EXPECTED_USER_PLACEHOLDERS.items():
        template = getattr(prompts, name)
        # Render with dummy values for every expected placeholder
        for placeholder in expected:
            assert f"{{{placeholder}}}" in template, (
                f"Prompt {name} is missing placeholder {{{placeholder}}}. "
                f"Update EXPECTED_USER_PLACEHOLDERS in this test if you removed it."
            )


def test_user_explain_renders_without_runtime_data_leaking():
    """USER_EXPLAIN_TEMPLATE formats cleanly with synthetic data."""
    rendered = prompts.USER_EXPLAIN_TEMPLATE.format(
        code="x = 1",
        line_number=1,
        line_content="x = 1",
        locals_json="{}",
    )
    assert "x = 1" in rendered
    # No unfilled str.format() placeholders remain.
    # (Curly braces in JSON examples are legitimate — only flag actual
    # identifier-style placeholders.)
    leftovers = PLACEHOLDER_RE.findall(rendered)
    assert not leftovers, f"Unfilled placeholders: {leftovers}"


def test_system_explain_does_not_have_placeholders():
    """The system prompt is fixed instructions only — runtime data goes in user prompt.

    Curly braces from inline JSON examples are fine. What we forbid are
    `str.format()`-style placeholders that a future caller might accidentally
    try to interpolate into.
    """
    leftovers = PLACEHOLDER_RE.findall(prompts.SYSTEM_EXPLAIN)
    assert not leftovers, (
        f"SYSTEM_EXPLAIN has str.format() placeholders: {leftovers}. "
        "Runtime data should live in USER_*_TEMPLATE, not the system message."
    )


def test_system_prompts_have_no_runtime_placeholders():
    """All SYSTEM_* prompts are static or only have {tag} (misconception-tag).

    Most SYSTEM_* prompts are fully static (the runtime data goes into the
    USER_*_TEMPLATE). The repair-related prompts use {tag} as a small,
    per-request injection that is formatted once before the stream starts.

    Curly braces in inline JSON examples (like `{\"key\": \"value\"}`) are
    legitimate; what we forbid is `{identifier}`-style placeholders other than
    `{tag}` in the repair prompts.
    """
    static_system_prompts = [
        "SYSTEM_EXPLAIN",
        "SYSTEM_GRADE_EXPLANATION",
        "SYSTEM_MISCONCEPTION",
    ]
    for name in static_system_prompts:
        value = getattr(prompts, name)
        leftovers = PLACEHOLDER_RE.findall(value)
        assert not leftovers, (
            f"{name} must be a static prompt — found placeholders: {leftovers}. "
            f"Runtime data should be passed via the matching USER_*_TEMPLATE."
        )

    # Repair prompts may use {tag} — it's the *only* allowed placeholder.
    for name in ("SYSTEM_REPAIR_GENERATE", "SYSTEM_GRADE_REPAIR"):
        value = getattr(prompts, name)
        leftovers = [p for p in PLACEHOLDER_RE.findall(value) if p != "{tag}"]
        assert not leftovers, (
            f"{name} only allows {{tag}} placeholder — found others: {leftovers}."
        )


def test_repair_prompts_use_tag_placeholder():
    """The repair prompts use {tag} so a specific misconception can be injected."""
    assert "{tag}" in prompts.SYSTEM_REPAIR_GENERATE
    assert "{tag}" in prompts.SYSTEM_GRADE_REPAIR


def test_fallback_dicts_have_required_keys():
    """Fallback responses must always have the keys the router returns."""
    assert set(prompts.FALLBACK_GRADING.keys()) >= {"score", "rating_suggestion", "feedback"}
    assert set(prompts.FALLBACK_MISCONCEPTION.keys()) >= {"tag", "explanation"}
    # And the values must be sensible
    assert isinstance(prompts.FALLBACK_GRADING["score"], int)
    assert 0 <= prompts.FALLBACK_GRADING["score"] <= 100


@pytest.mark.parametrize("name", list(EXPECTED_USER_PLACEHOLDERS.keys()))
def test_user_templates_render_round_trip(name):
    """Format each USER_*_TEMPLATE with every placeholder filled; assert no KeyError."""
    template = getattr(prompts, name)
    fillers = {
        "code": "x = 1",
        "line_number": "1",
        "line_content": "x = 1",
        "locals_json": "{}",
        "steps_json": "[]",
        "user_answer": "x becomes 1",
        "lineno": "1",
        "checkpoint_type": "variable_prediction",
        "variable_name": "x",
        "correct_value": "1",
        "user_prediction": "0",
        "original_code": "def f(): pass",
        "misconception_tag": "off_by_one",
        "user_fix": "def f(): pass",
    }
    rendered = template.format(**fillers)
    # No leftover str.format() placeholders after a round-trip
    # (curly braces in inline JSON examples are fine).
    leftovers = PLACEHOLDER_RE.findall(rendered)
    assert not leftovers, f"{name} left unrendered placeholders: {leftovers}"
