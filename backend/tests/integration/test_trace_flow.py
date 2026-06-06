"""Integration tests for the trace API endpoint."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    """Health endpoint should return healthy or degraded status depending on service availability."""
    response = client.get("/health")
    assert response.status_code in (200, 503)
    assert response.json()["status"] in ("healthy", "degraded")


def test_full_trace_flow():
    """POST valid code → 200 + steps array."""
    response = client.post(
        "/api/traces/run",
        json={"code": "x = 1\ny = x + 2"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "steps" in data
    assert data["total_steps"] > 0
    assert "duration_ms" in data


def test_side_effect_blocked():
    """import os should be blocked with 422."""
    response = client.post(
        "/api/traces/run",
        json={"code": "import os"}
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "SIDE_EFFECT_BLOCKED"


def test_syntax_error():
    """Syntax error should return 422."""
    response = client.post(
        "/api/traces/run",
        json={"code": "def :"}
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "SYNTAX_ERROR"


def test_empty_code():
    """Empty code should not crash."""
    response = client.post(
        "/api/traces/run",
        json={"code": ""}
    )
    # Empty code is technically valid Python (no-op)
    assert response.status_code in (200, 422)


def test_code_too_long():
    """Code over 5000 chars should be rejected."""
    response = client.post(
        "/api/traces/run",
        json={"code": "x = 1\n" * 3000}
    )
    assert response.status_code == 422
