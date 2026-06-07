"""Tests for FIX-MD-02: Branch detection marks all as taken."""


def test_branch_detection_only_marks_taken_branch():
    """
    MEDIUM-02: When if True: a=1 else: a=2 runs, only 'then' should be marked taken.
    The current code marks ALL branches as taken regardless of actual evaluation.
    """
    from tracer.tracer import run_trace

    code = """
x = 1
if x > 0:
    result = "positive"
else:
    result = "non-positive"
y = 2
"""
    result = run_trace(code)
    
    steps_with_branch = [s for s in result["steps"] if s.get("branches_taken")]
    
    assert len(steps_with_branch) > 0, "No branches detected"
    
    for step in steps_with_branch:
        branch_info = step["branches_taken"].get("if", {})
        # The branch that executed should have taken=True, branch="then" or "else"
        # The branch that did NOT execute should not appear
        if branch_info.get("taken") is True:
            assert branch_info.get("branch") in ("then", "else"), (
                f"MEDIUM-02: Branch taken={branch_info.get('taken')} but branch field is missing or invalid: {branch_info}. "
                "Branch detection must show which branch actually fired."
            )
            assert "condition" in branch_info, "Must show the actual condition expression"


def test_branch_detection_if_false():
    """When if False, 'else' branch should be marked taken."""
    from tracer.tracer import run_trace

    code = """
if False:
    x = 1
else:
    x = 2
"""
    result = run_trace(code)
    
    steps_with_branch = [s for s in result["steps"] if s.get("branches_taken")]
    for step in steps_with_branch:
        branch_info = step["branches_taken"].get("if", {})
        if branch_info.get("taken") is True:
            assert branch_info.get("branch") == "else", (
                f"MEDIUM-02: 'if False' should take 'else' branch, got: {branch_info}"
            )


def test_branch_detection_if_true():
    """When if True, 'then' branch should be marked taken."""
    from tracer.tracer import run_trace

    code = """
if True:
    y = 10
else:
    y = 20
"""
    result = run_trace(code)
    
    steps_with_branch = [s for s in result["steps"] if s.get("branches_taken")]
    for step in steps_with_branch:
        branch_info = step["branches_taken"].get("if", {})
        if branch_info.get("taken") is True:
            assert branch_info.get("branch") == "then", (
                f"MEDIUM-02: 'if True' should take 'then' branch, got: {branch_info}"
            )


def test_branch_detection_includes_condition():
    """Branch detection should include the condition expression."""
    from tracer.tracer import run_trace

    code = """
x = 5
if x > 3:
    z = 1
else:
    z = 0
"""
    result = run_trace(code)
    
    steps_with_branch = [s for s in result["steps"] if s.get("branches_taken")]
    found_condition = False
    for step in steps_with_branch:
        branch_info = step["branches_taken"].get("if", {})
        if branch_info.get("taken") is True:
            assert "condition" in branch_info, "Must include condition expression"
            found_condition = True
    
    assert found_condition, "No taken branch found with condition"
