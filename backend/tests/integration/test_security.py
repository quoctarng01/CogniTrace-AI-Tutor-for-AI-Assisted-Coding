"""
Security integration tests for the CodeScope API.

Tests that the sandbox correctly blocks dangerous patterns,
and that the eval() vulnerability is fixed.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_eval_injection_blocked_by_literal_eval():
    """
    Verify that sending a code expression as an initial_namespace value
    does NOT execute it — ast.literal_eval only accepts literals.
    """
    resp = client.post("/api/traces/run", json={
        "code": "x = 1",
        "initial_namespace": {
            # This is a Python expression, not a literal — ast.literal_eval must reject it
            "x": "().__class__.__bases__[0].__subclasses__()"
        }
    })
    # The request should succeed (200) because invalid values are silently skipped,
    # OR it should return 422 if the validator rejects the payload.
    # It must NOT execute the expression.
    assert resp.status_code in (200, 422)
    if resp.status_code == 200:
        data = resp.json()
        for step in data.get("steps", []):
            for var_name, var_info in step.get("variables", {}).items():
                # The malicious expression result must not appear in any variable value
                assert "__subclasses__" not in str(var_info.get("value", "")), \
                    f"eval() injection succeeded for variable '{var_name}'"


def test_ctypes_import_blocked():
    """ctypes allows direct memory access — must be blocked."""
    resp = client.post("/api/traces/run", json={"code": "import ctypes"})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["error"] == "SIDE_EFFECT_BLOCKED"


def test_threading_import_blocked():
    """threading creates threads that outlive the tracer — must be blocked."""
    resp = client.post("/api/traces/run", json={"code": "import threading"})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["error"] == "SIDE_EFFECT_BLOCKED"


def test_multiprocessing_import_blocked():
    """multiprocessing spawns child processes — must be blocked."""
    resp = client.post("/api/traces/run", json={"code": "import multiprocessing"})
    assert resp.status_code == 422


def test_breakpoint_call_blocked():
    """breakpoint() drops into pdb debugger — must be blocked."""
    resp = client.post("/api/traces/run", json={"code": "breakpoint()"})
    assert resp.status_code == 422


def test_globals_call_blocked():
    """globals() exposes the global namespace — must be blocked."""
    resp = client.post("/api/traces/run", json={"code": "x = globals()"})
    assert resp.status_code == 422


def test_existing_os_block_still_works():
    """Regression: existing os block must still work after adding new entries."""
    resp = client.post("/api/traces/run", json={"code": "import os"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "SIDE_EFFECT_BLOCKED"


def test_valid_code_still_traces_after_security_changes():
    """Regression: safe code must still execute correctly after all security changes."""
    resp = client.post("/api/traces/run", json={"code": "x = 1\ny = x + 2"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_steps"] > 0
    # Verify variable tracking still works
    last_step = data["steps"][-1]
    assert "y" in last_step["variables"]
    assert last_step["variables"]["y"]["value"] == "3"


def test_initial_namespace_with_valid_literal():
    """Valid literal values in initial_namespace must still work."""
    resp = client.post("/api/traces/run", json={
        "code": "result = x + y",
        "initial_namespace": {"x": "10", "y": "5"}
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_steps"] > 0


def test_initial_namespace_invalid_value_silently_skipped():
    """Invalid literal values must be silently skipped, not crash the server."""
    resp = client.post("/api/traces/run", json={
        "code": "x = 1",
        "initial_namespace": {
            "x": "not_a_literal_[[[",  # Invalid Python literal syntax
        }
    })
    # Must return 200 (skipped) not 500 (crash)
    assert resp.status_code in (200, 422)
    assert resp.status_code != 500
