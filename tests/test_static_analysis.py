# tests/test_static_analysis.py
from backend.analyzers.static_analysis import (
    Annotation,
    analyze_code,
)


# ---------------------------------------------------------------------------
# Pattern 1: missing_none_guard
# ---------------------------------------------------------------------------

def test_missing_none_guard__flagged():
    """`if x == value:` without None guard is flagged as TypeError risk."""
    code = "if x == 'hello':\n    print('yes')"
    result = analyze_code(code)
    flags = [a for a in result if a.pattern_id == "missing_none_guard"]
    assert len(flags) == 1
    assert flags[0].line == 1
    assert flags[0].severity == "high"


def test_missing_none_guard__absent_when_is_not_none():
    """`if x is not None:` should NOT be flagged."""
    code = "if x is not None:\n    print('yes')"
    result = analyze_code(code)
    flags = [a for a in result if a.pattern_id == "missing_none_guard"]
    assert len(flags) == 0


def test_missing_none_guard__absent_when_x_is_none_check():
    """`if x == value and x is not None:` should NOT be flagged."""
    code = "if x == value and x is not None:\n    print('yes')"
    result = analyze_code(code)
    flags = [a for a in result if a.pattern_id == "missing_none_guard"]
    assert len(flags) == 0


def test_missing_none_guard__not_flagged_for_private_names():
    """Dunder names (e.g., __debug__) are not flagged."""
    code = "if __debug__:\n    print('yes')"
    result = analyze_code(code)
    flags = [a for a in result if a.pattern_id == "missing_none_guard"]
    assert len(flags) == 0


# ---------------------------------------------------------------------------
# Pattern 2: mutable_default
# ---------------------------------------------------------------------------

def test_mutable_default__list__flagged():
    """`def foo(x=[])` should be flagged."""
    code = "def foo(x=[]):\n    x.append(1)\n    return x"
    result = analyze_code(code)
    assert len(result) == 1
    assert result[0].pattern_id == "mutable_default"
    assert result[0].line == 1
    assert result[0].severity == "high"


def test_mutable_default__dict__flagged():
    """`def bar(data={})` should be flagged."""
    code = "def bar(data={}):\n    data['key'] = 'value'\n    return data"
    result = analyze_code(code)
    assert len(result) == 1
    assert result[0].pattern_id == "mutable_default"
    assert result[0].severity == "high"


def test_mutable_default__set__flagged():
    """`def baz(items=set())` should be flagged."""
    code = "def baz(items=set()):\n    items.add(1)\n    return items"
    result = analyze_code(code)
    flags = [a for a in result if a.pattern_id == "mutable_default"]
    assert len(flags) == 1
    assert flags[0].severity == "high"


def test_mutable_default__none_is_fine():
    """`def foo(x=None)` is NOT flagged."""
    code = "def foo(x=None):\n    if x is None: x = []\n    return x"
    result = analyze_code(code)
    flags = [a for a in result if a.pattern_id == "mutable_default"]
    assert len(flags) == 0


def test_mutable_default__immutable_default_is_fine():
    """`def foo(x=0)`, `def foo(s='')` are NOT flagged."""
    for default in ("0", "''", "True", "42.5"):
        code = f"def foo(x={default}):\n    return x"
        result = analyze_code(code)
        flags = [a for a in result if a.pattern_id == "mutable_default"]
        assert len(flags) == 0, f"Failed for default={default}"


def test_mutable_default__lambda_is_ignored():
    """Lambdas don't need None guards — skip them (lambdas can't have defaults in Python)."""
    code = "f = lambda x: x + 1"
    result = analyze_code(code)
    flags = [a for a in result if a.pattern_id == "mutable_default"]
    assert len(flags) == 0


# ---------------------------------------------------------------------------
# Pattern 3: comprehension_filter
# ---------------------------------------------------------------------------

def test_comprehension_filter__attribute_access__flagged():
    """`[x.strip() for x in items if x.strip()]` is flagged as overly aggressive."""
    code = "[x.strip() for x in items if x.strip()]"
    result = analyze_code(code)
    flags = [a for a in result if a.pattern_id == "comprehension_filter"]
    assert len(flags) == 1
    assert flags[0].severity == "medium"


def test_comprehension_filter__multiple_filters__flagged():
    """Multiple filters on a comprehension are flagged."""
    code = "[x for x in items if x > 0 if x < 10]"
    result = analyze_code(code)
    flags = [a for a in result if a.pattern_id == "comprehension_filter"]
    assert len(flags) == 1
    assert flags[0].severity == "medium"


def test_comprehension_filter__single_simple_filter__not_flagged():
    """A simple `[x for x in items if x > 0]` is not flagged."""
    code = "[x for x in items if x > 0]"
    result = analyze_code(code)
    flags = [a for a in result if a.pattern_id == "comprehension_filter"]
    assert len(flags) == 0


def test_comprehension_filter__dict_comprehension__not_flagged():
    """Dict comprehensions are out of scope for this pattern."""
    code = "{k: v for k, v in items if k}"
    result = analyze_code(code)
    flags = [a for a in result if a.pattern_id == "comprehension_filter"]
    assert len(flags) == 0


# ---------------------------------------------------------------------------
# Pattern 4: implicit_truthiness
# ---------------------------------------------------------------------------

def test_implicit_truthiness__bare_name__flagged():
    """`if data:` where data is a bare name is flagged."""
    code = "if data:\n    print('has data')"
    result = analyze_code(code)
    flags = [a for a in result if a.pattern_id == "implicit_truthiness"]
    assert len(flags) == 1
    assert flags[0].line == 1
    assert flags[0].severity == "medium"


def test_implicit_truthiness__absent_for_comparison():
    """`if len(data) > 0:` is NOT flagged as implicit truthiness."""
    code = "if len(data) > 0:\n    print('has data')"
    result = analyze_code(code)
    flags = [a for a in result if a.pattern_id == "implicit_truthiness"]
    assert len(flags) == 0


def test_implicit_truthiness__absent_for_obvious_booleans():
    """Flag names like `is_active`, `done`, `ok` are not flagged."""
    for name in ("is_active", "done", "ok", "flag", "enabled"):
        code = f"if {name}:\n    print('yes')"
        result = analyze_code(code)
        flags = [a for a in result if a.pattern_id == "implicit_truthiness"]
        assert len(flags) == 0, f"Failed for name={name}"


def test_implicit_truthiness__not_flagged_for_attribute_access():
    """`if user.is_active:` is not flagged."""
    code = "if user.is_active:\n    print('active')"
    result = analyze_code(code)
    flags = [a for a in result if a.pattern_id == "implicit_truthiness"]
    assert len(flags) == 0


# ---------------------------------------------------------------------------
# Pattern 5: requests_no_timeout
# ---------------------------------------------------------------------------

def test_requests_no_timeout__get__flagged():
    """`requests.get(url)` without timeout is flagged."""
    code = "import requests\nrequests.get('https://example.com')"
    result = analyze_code(code)
    flags = [a for a in result if a.pattern_id == "requests_no_timeout"]
    assert len(flags) == 1
    assert flags[0].line == 2
    assert flags[0].severity == "high"


def test_requests_no_timeout__post__flagged():
    """`requests.post(url)` without timeout is flagged."""
    code = "import requests\nrequests.post('https://example.com', json={'key': 'value'})"
    result = analyze_code(code)
    flags = [a for a in result if a.pattern_id == "requests_no_timeout"]
    assert len(flags) == 1


def test_requests_no_timeout__with_timeout__not_flagged():
    """`requests.get(url, timeout=5)` is NOT flagged."""
    code = "import requests\nrequests.get('https://example.com', timeout=5)"
    result = analyze_code(code)
    flags = [a for a in result if a.pattern_id == "requests_no_timeout"]
    assert len(flags) == 0


def test_requests_no_timeout__no_import__not_flagged():
    """If `requests` is not imported, we can't detect it — not flagged."""
    code = "get('https://example.com')"
    result = analyze_code(code)
    flags = [a for a in result if a.pattern_id == "requests_no_timeout"]
    assert len(flags) == 0


# ---------------------------------------------------------------------------
# General / edge cases
# ---------------------------------------------------------------------------

def test_syntax_error__returns_empty():
    """Malformed code returns an empty list, not an exception."""
    code = "def foo(:\n    pass"
    result = analyze_code(code)
    assert result == []


def test_multiple_patterns_in_same_code__all_detected():
    """Multiple patterns in one snippet are all detected."""
    code = (
        "def process(items=[]):\n"
        "    if data:\n"
        "        pass\n"
    )
    result = analyze_code(code)
    pattern_ids = {a.pattern_id for a in result}
    assert "mutable_default" in pattern_ids
    assert "implicit_truthiness" in pattern_ids


def test_no_annotations__returns_empty_list():
    """Clean code returns an empty list."""
    code = (
        "def greet(name=None):\n"
        "    if name is not None:\n"
        "        return f'Hello, {name}'\n"
        "    return 'Hello'\n"
    )
    result = analyze_code(code)
    assert result == []


def test_line_numbers_are_correct():
    """Line numbers match the actual source."""
    code = (
        "def add(a, b):\n"       # line 1
        "    return a + b\n"      # line 2
        "result = add(1, 2)\n"   # line 3
    )
    result = analyze_code(code)
    assert result == []  # No bugs here


def test_annotation_has_required_fields():
    """Every annotation has all required fields populated."""
    code = "def foo(x=[]): pass"
    result = analyze_code(code)
    for ann in result:
        assert ann.line > 0
        assert ann.severity in ("high", "medium", "low")
        assert ann.pattern_id
        assert ann.message
        assert ann.suggestion


def test_deduplication__same_line_same_pattern():
    """Duplicate annotations on the same line/pattern are deduplicated."""
    code = "def foo(x=[]):\n    pass\n    pass"
    result = analyze_code(code)
    lines = [a.line for a in result]
    pattern_ids = [a.pattern_id for a in result]
    # Should have exactly one mutable_default annotation
    assert pattern_ids.count("mutable_default") == 1


def test_nested_functions__both_checked():
    """Nested functions are also checked for mutable defaults."""
    code = (
        "def outer(x=[]):\n"
        "    def inner(y=[]):\n"
        "        pass\n"
        "    return inner"
    )
    result = analyze_code(code)
    flags = [a for a in result if a.pattern_id == "mutable_default"]
    assert len(flags) == 2  # Both outer and inner have mutable defaults
