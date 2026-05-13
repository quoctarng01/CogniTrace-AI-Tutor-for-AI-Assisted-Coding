"""Tests for FIX-MD-04: Debug print statements in llm_router.py."""
import inspect


def test_no_print_statements_in_llm_router():
    """MEDIUM-04: llm_router.py should not have print() statements."""
    from app.services import llm_router

    source = inspect.getsource(llm_router)

    # Check for print statements (not in docstrings or comments)
    lines = source.split('\n')
    print_lines = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Skip comment lines and docstrings
        if stripped.startswith('#'):
            continue
        if '"""' in stripped or "'''" in stripped:
            continue
        # Find actual print( calls
        if 'print(' in stripped:
            print_lines.append((i, line))

    assert len(print_lines) == 0, (
        f"MEDIUM-04: Found {len(print_lines)} print() statements in llm_router.py:\n"
        + "\n".join(f"  Line {n}: {line}" for n, line in print_lines)
        + "\nReplace all print() with logger.debug() or logger.info()."
    )
