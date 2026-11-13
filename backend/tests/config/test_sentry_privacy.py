"""Projection tests; these never contact Sentry."""
from datetime import datetime, timezone

from config.sentry_privacy import before_send, before_send_transaction


def test_exception_projection_preserves_safe_frame_and_drops_sensitive_fields():
    secret = "SECRET_SENTINEL_123"
    event = {
        "event_id": "a" * 32, "timestamp": datetime.now(timezone.utc), "message": secret,
        "request": {"url": "https://site/?token=" + secret, "headers": {"Authorization": secret}, "data": secret},
        "user": {"email": secret}, "extra": {"secret": secret}, "breadcrumbs": {"values": [{"message": secret}]},
        "exception": {"values": [{"type": "ValueError", "value": secret, "stacktrace": {"frames": [
            {"in_app": True, "filename": "/srv/app/workflow.py", "function": "issue", "lineno": 42,
             "vars": {"secret": secret}, "context_line": secret},
            {"in_app": False, "filename": "other.py", "function": "outside", "lineno": 2},
        ]}}]},
    }
    result = before_send(event, {})
    assert secret not in str(result)
    value = result["exception"]["values"][0]
    assert value["type"] == "ValueError"
    assert value["stacktrace"]["frames"] == [{"filename": "workflow.py", "function": "issue", "lineno": 42, "in_app": True}]


def test_transaction_projection_removes_url_spans_and_all_untrusted_metadata():
    secret = "SECRET_SENTINEL_123"
    event = {"event_id": "a" * 32, "type": "transaction", "transaction": "/?secret=" + secret,
             "start_timestamp": 1.0, "timestamp": 2.0, "request": {"headers": {"cookie": secret}},
             "contexts": {"trace": {"trace_id": "b" * 32, "span_id": "c" * 16, "data": {"secret": secret}}},
             "spans": [{"description": secret}], "breadcrumbs": [{"message": secret}]}
    result = before_send_transaction(event, {})
    assert secret not in str(result)
    assert result["transaction"] == "[redacted]"
    assert result["contexts"] == {"trace": {"trace_id": "b" * 32, "span_id": "c" * 16}}
    assert "spans" not in result and "request" not in result


def test_malformed_events_are_dropped():
    assert before_send({"exception": {"values": [{"type": []}]}}, {}) is None
    assert before_send({"message": "secret"}, {}) is None
    assert before_send_transaction({"contexts": {"trace": {"trace_id": "bad"}}}, {}) is None


def test_sdk_serialized_iso_timestamps_are_normalized_and_secrets_rejected():
    event = {"type": "transaction", "start_timestamp": "2026-11-08T12:30:01.123456Z",
             "timestamp": "2026-11-08T12:30:02.123456Z", "transaction": "SECRET_SENTINEL",
             "contexts": {"trace": {"trace_id": "b" * 32, "span_id": "c" * 16}}}
    result = before_send_transaction(event, {})
    assert isinstance(result["start_timestamp"], float)
    assert result["timestamp"] > result["start_timestamp"]
    assert "SECRET_SENTINEL" not in str(result)
    event["timestamp"] = "2026-11-08T12:30:02ZSECRET_SENTINEL"
    assert before_send_transaction(event, {}) is None
    for invalid in (float("nan"), float("inf"), -1, 99999999999, True, "2026-99-99T12:30:02Z"):
        event["timestamp"] = invalid
        assert before_send_transaction(event, {}) is None


def test_unexpected_or_nonempty_attachment_container_fails_closed():
    event = {"exception": {"values": [{"type": "ValueError"}]}}
    for hint in ({"attachments": ["secret"]}, {"attachments": ""}, {"attachments": {}}, {"attachments": False}):
        assert before_send(event, hint) is None
    for hint in ({}, {"attachments": None}, {"attachments": []}, {"attachments": ()}):
        assert before_send(event, hint) is not None
