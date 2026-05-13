"""Tests for FIX-MD-06: concept_tags and is_public silently dropped on save."""
import inspect


def test_save_trace_includes_concept_tags_and_is_public():
    """MEDIUM-06: SaveTraceRequest must include concept_tags AND is_public in trace_data."""
    from app.routers.traces import SaveTraceRequest, save_trace

    # Verify SaveTraceRequest model accepts both fields
    model_source = inspect.getsource(SaveTraceRequest)
    assert "concept_tags" in model_source, (
        "MEDIUM-06: SaveTraceRequest missing concept_tags field"
    )
    assert "is_public" in model_source, (
        "MEDIUM-06: SaveTraceRequest missing is_public field"
    )

    # Verify save_trace endpoint includes both in trace_data
    func_source = inspect.getsource(save_trace)

    # Check both fields are present in trace_data dict
    assert '"concept_tags"' in func_source or "'concept_tags'" in func_source, (
        "MEDIUM-06: save_trace doesn't include concept_tags in trace_data. "
        "Fields are silently dropped when saving to Supabase."
    )
    assert '"is_public"' in func_source or "'is_public'" in func_source, (
        "MEDIUM-06: save_trace doesn't include is_public in trace_data."
    )
