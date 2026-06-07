"""Unit tests for review timestamp — FIX-HI-01."""
import inspect


def test_last_reviewed_at_not_string_now():
    """HI-01: last_reviewed_at should be ISO timestamp, not the string 'now()'."""
    import app.routers.review as review_module
    
    source = inspect.getsource(review_module)
    
    assert '"now()"' not in source, (
        "HI-01: last_reviewed_at uses string 'now()' instead of datetime. "
        "Supabase will store the literal string 'now()', not a timestamp."
    )
