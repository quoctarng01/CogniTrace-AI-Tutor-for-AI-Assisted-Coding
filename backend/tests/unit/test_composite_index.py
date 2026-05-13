"""Tests for FIX-MD-05: Missing composite index on review_cards."""
import os

def test_composite_index_exists():
    """MEDIUM-05: review_cards should have composite index on (user_id, next_review_date)."""
    # Find the migration file
    backend_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    migration_path = os.path.join(backend_path, "migrations", "V001__initial_schema.sql")
    
    with open(migration_path) as f:
        content = f.read()
    
    assert "idx_review_cards_user_next_date" in content, (
        "MEDIUM-05: Missing composite index on review_cards(user_id, next_review_date). "
        "Dashboard query filters by both columns — composite index needed for performance."
    )
    assert "user_id, next_review_date" in content, (
        "Index should cover both columns in the right order."
    )
