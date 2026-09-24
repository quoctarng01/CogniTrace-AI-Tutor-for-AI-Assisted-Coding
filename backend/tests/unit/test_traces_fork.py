"""Unit tests for trace forking endpoint."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_fork_trace_from_step():
    code = """
x = 5
y = x * 2
z = x + y
"""
    # Fork from step 1 with override x = 100
    payload = {
        "code": code,
        "fork_step_number": 1,
        "overridden_variables": {"x": "100"},
    }

    response = client.post("/api/traces/fork", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "steps" in data
    assert data["fork_step_number"] == 1
    assert data["overridden_variables"]["x"] == "100"

    # Verify that x starts as 100 in step 0 of the forked execution
    first_step_vars = data["steps"][0]["variables"]
    assert "x" in first_step_vars
    assert first_step_vars["x"]["value"] == "100"


def test_fork_trace_sandbox_blocking():
    code = "import os"
    payload = {
        "code": code,
        "fork_step_number": 0,
        "overridden_variables": {},
    }
    response = client.post("/api/traces/fork", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "SIDE_EFFECT_BLOCKED"
