import io
import json

import pytest
from urllib.error import HTTPError

from apps.integrations.models_endpoints import NotificationEndpoint
from apps.integrations.notification_delivery import ensure_deliveries, send
from apps.integrations.notification_outbox import emit
from apps.integrations.notification_sources import NotificationSource, SOURCES

pytestmark = pytest.mark.django_db


@pytest.fixture
def intent(telegram_account, begin, webhook, monkeypatch):
    _, code, _ = begin()
    assert webhook(code).status_code == 200
    c = telegram_account
    monkeypatch.setitem(SOURCES, "telegram.test", NotificationSource(lambda _: True))
    monkeypatch.setattr("apps.integrations.notification_catalog.is_notification_enabled", lambda *args: True)
    return emit(makerspace=c.space, recipient=c.user, feature="hardware_requests", stream="hardware",
        event="accepted", audience="requester", source_kind="telegram.test", source_id=1,
        dedup_key="telegram:outbox:test", rendered={"subject": "Loan", "text": "Your loan was accepted."})


def test_shared_outbox_accepts_real_telegram_provider(intent, bot_http):
    row = ensure_deliveries(intent).get(channel="telegram")
    bot_http.responses.append({"ok": True, "result": {"message_id": 100}})
    send(row.pk)
    row.refresh_from_db()
    assert row.state == "accepted" and row.provider_id == "100" and row.attempt_count == 1
    count = len(bot_http.calls)
    send(row.pk)
    assert len(bot_http.calls) == count


def test_shared_outbox_schedules_rate_limit_retry(intent, bot_http):
    row = ensure_deliveries(intent).get(channel="telegram")
    body = json.dumps({"ok": False, "parameters": {"retry_after": 600}}).encode()
    bot_http.responses.append(HTTPError("https://telegram.invalid", 429, "rate", {}, io.BytesIO(body)))
    send(row.pk)
    row.refresh_from_db()
    assert row.state == "retrying" and row.retryable and row.last_error == "rate_limited"
    assert row.next_attempt_at and row.claim_until is None


def test_shared_outbox_stops_after_block_and_revokes(intent, bot_http):
    row = ensure_deliveries(intent).get(channel="telegram")
    bot_http.responses.append({"ok": False, "error_code": 403})
    send(row.pk)
    row.refresh_from_db()
    assert row.state == "failed" and not row.retryable and row.last_error == "invalid_endpoint"
    assert NotificationEndpoint.objects.get().verification_state == "revoked"
