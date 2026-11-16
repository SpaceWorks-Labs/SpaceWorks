"""Exercise the SDK serialization and envelope path without network or SDK threads."""
from datetime import datetime, timedelta, timezone

from sentry_sdk.client import Client
from sentry_sdk.attachments import Attachment
from sentry_sdk.transport import Transport

from config.sentry_privacy import before_send, before_send_transaction


class MemoryTransport(Transport):
    def __init__(self):
        super().__init__()
        self.envelopes = []

    def capture_envelope(self, envelope):
        self.envelopes.append(envelope)


def client_with_transport():
    transport = MemoryTransport()
    client = Client(
        dsn="https://public@example.invalid/1", transport=transport,
        default_integrations=False, auto_session_tracking=False,
        enable_backpressure_handling=False, send_client_reports=False,
        _experiments={"enable_metrics": False},
        max_request_body_size="never", include_local_variables=False,
        include_source_context=False, send_default_pii=False,
        traces_sample_rate=1.0, before_send=before_send,
        before_send_transaction=before_send_transaction,
    )
    return client, transport


def test_sdk_error_envelope_excludes_private_sentinels_and_keeps_useful_frame():
    client, transport = client_with_transport()
    secret = "SENTRY_PRIVATE_SENTINEL_27"
    event = {
        "timestamp": datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc),
        "message": secret, "user": {"email": secret}, "extra": {"secret": secret},
        "request": {"url": f"https://example.test/?token={secret}", "data": secret,
                    "headers": {"Authorization": secret, "Cookie": secret}},
        "breadcrumbs": {"values": [{"message": secret}]},
        "exception": {"values": [{"type": "ValueError", "value": secret, "stacktrace": {"frames": [
            {"filename": "/app/apps/workflow.py", "function": "issue", "lineno": 42,
             "in_app": True, "vars": {"secret": secret}, "context_line": secret},
        ]}}]},
    }
    try:
        assert client.capture_event(event) is not None
        assert len(transport.envelopes) == 1
        envelope = transport.envelopes[0]
        assert secret.encode() not in envelope.serialize()
        value = envelope.get_event()["exception"]["values"][0]
        assert value["type"] == "ValueError"
        assert value["stacktrace"]["frames"] == [{"filename": "workflow.py", "function": "issue", "lineno": 42, "in_app": True}]
    finally:
        client.close()


def test_sdk_transaction_envelope_preserves_duration_without_sensitive_values():
    client, transport = client_with_transport()
    secret = "SENTRY_PRIVATE_SENTINEL_27"
    start = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)
    event = {
        "type": "transaction", "transaction": f"/invite?token={secret}",
        "start_timestamp": start, "timestamp": start + timedelta(seconds=2),
        "contexts": {"trace": {"trace_id": "a" * 32, "span_id": "b" * 16, "data": {"secret": secret}}},
        "request": {"headers": {"Cookie": secret}, "url": f"https://example.test/?token={secret}"},
        "user": {"email": secret}, "extra": {"secret": secret},
        "breadcrumbs": {"values": [{"message": secret}]},
        "spans": [{"span_id": "c" * 16, "trace_id": "a" * 32, "description": secret,
                   "start_timestamp": start, "timestamp": start + timedelta(seconds=1)}],
    }
    try:
        assert client.capture_event(event) is not None
        assert len(transport.envelopes) == 1
        envelope = transport.envelopes[0]
        assert secret.encode() not in envelope.serialize()
        transaction = envelope.get_transaction_event()
        assert transaction["transaction"] == "[redacted]"
        assert transaction["timestamp"] - transaction["start_timestamp"] == 2
        assert not transaction.get("spans")
    finally:
        client.close()


def test_sdk_drops_error_and_transaction_with_attachments_before_envelope():
    client, transport = client_with_transport()
    private = b"PRIVATE_ATTACHMENT_SENTINEL"
    attachment = Attachment(bytes=private, filename="private.txt", add_to_transactions=True)
    start = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)
    error = {"timestamp": start, "exception": {"values": [{"type": "ValueError"}]}}
    transaction = {"type": "transaction", "start_timestamp": start,
                   "timestamp": start + timedelta(seconds=2),
                   "contexts": {"trace": {"trace_id": "a" * 32, "span_id": "b" * 16}}}
    try:
        assert client.capture_event(error, hint={"attachments": [attachment]}) is None
        assert client.capture_event(transaction, hint={"attachments": [attachment]}) is None
        assert transport.envelopes == []
        # Empty attachment lists remain valid for normal diagnostics.
        assert client.capture_event({"timestamp": start, "exception": {"values": [{"type": "ValueError"}]}},
                                    hint={"attachments": []}) is not None
        assert len(transport.envelopes) == 1
        assert private not in transport.envelopes[0].serialize()
    finally:
        client.close()
