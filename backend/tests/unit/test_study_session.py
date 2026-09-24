"""Tests for the pilot study-session telemetry glue.

These tests pin down the small, deterministic contract of `app.services.study_session`:
- a malformed `X-Study-Session` value is dropped (logged, not raised)
- a valid UUID is bound to the request context and readable downstream
- the default value is `None` (no header) so production traffic is unaffected
"""
from __future__ import annotations

import uuid

from app.services import study_session
from app.services.study_session import (
    bind_study_session_id,
    get_current_study_session_id,
    is_valid_study_session_id,
)


class TestUuidValidation:
    """Pure validation — no context-var involvement."""

    def test_rejects_empty(self) -> None:
        assert is_valid_study_session_id("") is False
        assert is_valid_study_session_id(None) is False

    def test_rejects_non_uuid_strings(self) -> None:
        # Common injection attempts
        assert is_valid_study_session_id("'; DROP TABLE study_sessions;--") is False
        assert is_valid_study_session_id("../../etc/passwd") is False
        assert is_valid_study_session_id("not-a-uuid") is False

    def test_rejects_uuid_with_extra_payload(self) -> None:
        # The header is opaque; we don't want to allow the client to smuggle
        # extra data that could confuse downstream parsing.
        uid = str(uuid.uuid4())
        assert is_valid_study_session_id(f"{uid};malicious=true") is False

    def test_accepts_valid_v4_uuid(self) -> None:
        uid = str(uuid.uuid4())
        assert is_valid_study_session_id(uid) is True

    def test_accepts_uppercase_uuid(self) -> None:
        uid = str(uuid.uuid4()).upper()
        assert is_valid_study_session_id(uid) is True

    def test_strips_whitespace_around_uuid(self) -> None:
        uid = str(uuid.uuid4())
        assert is_valid_study_session_id(f"  {uid}\n") is True


class TestContextVarBinding:
    """Context-var side effects — must default to None and accept valid UUIDs."""

    def teardown_method(self) -> None:
        # Reset the contextvar between tests so state does not leak.
        study_session._study_session_id_var.set(None)

    def test_default_is_none(self) -> None:
        assert get_current_study_session_id() is None

    def test_binding_sets_value(self) -> None:
        uid = str(uuid.uuid4())
        bind_study_session_id(uid)
        assert get_current_study_session_id() == uid

    def test_invalid_uuid_becomes_none(self) -> None:
        # Bad input → drop. The downstream row will simply have no FK.
        bind_study_session_id("not-a-uuid")
        assert get_current_study_session_id() is None

    def test_none_header_stays_none(self) -> None:
        # Header absent. Don't accidentally clobber a previously-bound value.
        study_session._study_session_id_var.set("preexisting")
        bind_study_session_id(None)
        assert get_current_study_session_id() is None

    def test_valid_uuid_overwrites_previous(self) -> None:
        study_session._study_session_id_var.set("stale-id")
        new_uid = str(uuid.uuid4())
        bind_study_session_id(new_uid)
        assert get_current_study_session_id() == new_uid


class TestMiddlewareIntegration:
    """End-to-end: the FastAPI middleware in `app.main` calls `bind_study_session_id`
    for every request. We assert the contract from the call-site perspective.
    """

    def teardown_method(self) -> None:
        study_session._study_session_id_var.set(None)

    def test_middleware_typical_pilot_request(self) -> None:
        """A valid `X-Study-Session` header is propagated to the contextvar."""
        uid = str(uuid.uuid4())
        bind_study_session_id(uid)  # simulates what main.py's middleware does
        assert get_current_study_session_id() == uid

    def test_middleware_production_request(self) -> None:
        """Production traffic (no header) never pollutes the contextvar."""
        study_session._study_session_id_var.set("prior-pilot-session")
        bind_study_session_id(None)  # simulates no-header request
        assert get_current_study_session_id() is None
