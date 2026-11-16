import io
import json
import logging
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from apps.audit.models import AuditLog
from apps.integrations.models_endpoints import NotificationEndpoint
from apps.integrations.models_destinations import NotificationDestination
from apps.integrations.notification_providers import provider_for
from apps.integrations.notification_telegram_transport import call
from apps.integrations.telegram import send_message

pytestmark = pytest.mark.django_db


@pytest.fixture
def linked(telegram_account, begin, webhook):
    _, code, _ = begin()
    assert webhook(code).status_code == 200
    endpoint = NotificationEndpoint.objects.get()
    c = telegram_account
    delivery = SimpleNamespace(pk=1, makerspace_id=c.space.pk, endpoint_id=endpoint.pk, endpoint=endpoint,
        integration_generation=c.config.generation, integration_identity=c.config.integration_identity,
        envelope=SimpleNamespace(recipient_id=c.user.pk, audience="requester"))
    return SimpleNamespace(account=c, endpoint=endpoint, delivery=delivery, provider=provider_for(c.config))


def test_dm_is_plain_text_without_keyboards(linked, bot_http):
    bot_http.responses.append({"ok": True, "result": {"message_id": 12}})
    result = linked.provider.send(linked.delivery, {"text": "<b>Borrowed</b> *tool*", "html": "<b>secret</b>",
        "reply_markup": {"inline_keyboard": [[{"callback_data": "accept:1"}]]}, "parse_mode": "HTML"})
    assert result.accepted and result.provider_id == "12"
    request, timeout = bot_http.calls[-1]
    assert request.full_url == "https://telegram.invalid/bot12345:private-token/sendMessage"
    assert timeout == 5
    assert json.loads(request.data) == {"chat_id": "789", "text": "<b>Borrowed</b> *tool*"}


def test_dm_trims_to_telegram_limit(linked, bot_http):
    bot_http.responses.append({"ok": True, "result": {"message_id": 13}})
    assert linked.provider.send(linked.delivery, {"text": "a" * 10000}).accepted
    payload = json.loads(bot_http.calls[-1][0].data)
    assert len(payload["text"]) <= 4096
    assert set(payload) == {"chat_id", "text"}


@pytest.mark.parametrize("http_status", [True, False])
def test_rate_limit_preserves_retry_after_without_revoking(linked, bot_http, http_status):
    data = {"ok": False, "error_code": 429, "parameters": {"retry_after": 123}, "description": "private-token 789"}
    bot_http.responses.append(HTTPError("https://telegram.invalid", 429, "rate", {}, io.BytesIO(json.dumps(data).encode()))
                              if http_status else data)
    result = linked.provider.send(linked.delivery, {"text": "private body"})
    assert not result.accepted and result.retryable and result.error_code == "rate_limited"
    assert result.retry_after == 123
    linked.endpoint.refresh_from_db()
    assert linked.endpoint.revoked_at is None
    assert "private-token" not in str(result) and "private body" not in str(result)


@pytest.mark.parametrize("delay,expected", [(999999, 3600), (-100, 1), ("abc", None), (True, None)])
def test_retry_after_is_bounded(linked, bot_http, delay, expected):
    bot_http.responses.append({"ok": False, "error_code": 429, "parameters": {"retry_after": delay}})
    assert linked.provider.send(linked.delivery, {"text": "body"}).retry_after == expected


@pytest.mark.parametrize("http_status", [True, False])
def test_blocked_bot_revokes_endpoint_once(linked, bot_http, http_status):
    data = {"ok": False, "error_code": 403, "description": "bot was blocked by the user"}
    bot_http.responses.append(HTTPError("https://telegram.invalid", 403, "forbidden", {}, io.BytesIO(json.dumps(data).encode()))
                              if http_status else data)
    result = linked.provider.send(linked.delivery, {"text": "body"})
    assert result.error_code == "invalid_endpoint" and not result.retryable
    linked.endpoint.refresh_from_db()
    assert linked.endpoint.revoked_at and linked.endpoint.verification_state == "revoked"
    assert AuditLog.objects.filter(action="notification.endpoint_revoked").count() == 1
    count = len(bot_http.calls)
    assert linked.provider.send(linked.delivery, {"text": "body"}).error_code == "invalid_endpoint"
    assert len(bot_http.calls) == count
    assert AuditLog.objects.filter(action="notification.endpoint_revoked").count() == 1


@pytest.mark.parametrize("error,code,ambiguous", [
    (TimeoutError("private-token"), "timeout", True),
    (URLError(TimeoutError("private-token")), "timeout", True),
    (URLError("private-token"), "unavailable", False),
])
def test_transport_failures_are_safe_and_typed(linked, bot_http, caplog, error, code, ambiguous):
    bot_http.responses.append(error)
    with caplog.at_level(logging.DEBUG):
        result = linked.provider.send(linked.delivery, {"text": "private body"})
    assert result.retryable and result.error_code == code and result.ambiguous == ambiguous
    assert "private-token" not in caplog.text and "private body" not in caplog.text
    assert "private-token" not in str(result)


@pytest.mark.parametrize("response", [{"ok": False, "error_code": 500}, [], {"ok": True, "result": None}])
def test_bad_upstream_response_never_crashes(linked, bot_http, response):
    bot_http.responses.append(response)
    result = linked.provider.send(linked.delivery, {"text": "body"})
    assert not result.accepted


def test_missing_message_id_is_ambiguous(linked, bot_http):
    bot_http.responses.append({"ok": True, "result": {}})
    result = linked.provider.send(linked.delivery, {"text": "body"})
    assert result.ambiguous and result.retryable and result.error_code == "timeout"


def test_room_provider_wraps_existing_transport(telegram_account, monkeypatch):
    from apps.integrations.models import NotificationDeliveryLog
    c = telegram_account
    room = NotificationDestination.objects.create(makerspace=c.space, channel="telegram", label="Staff", telegram_chat_id="-100")
    calls = []
    monkeypatch.setattr("apps.integrations.telegram.send_message", lambda *args, **kwargs: calls.append((args, kwargs)) or True)
    assert provider_for(c.config).test(room).accepted
    assert calls == [((c.space, "Space Works test alert."), {"destination": room})]
    log = NotificationDeliveryLog.objects.create(makerspace=c.space, channel="telegram", destination=room,
        destination_label=room.label, feature="hardware_requests", event="submitted", text_body="Staff summary")
    assert provider_for(c.config).send(log, {"text": log.text_body}).accepted
    assert calls[-1] == ((c.space, "Staff summary"), {"destination": room})
    log.destination = None
    assert provider_for(c.config).send(log, {"text": log.text_body}).error_code == "invalid_endpoint"
    assert len(calls) == 2


def test_room_payload_and_legacy_fallback_unchanged(telegram_account, bot_http):
    c = telegram_account
    c.config.set_credentials({})
    c.config.save(update_fields=["credentials"])
    c.space.set_telegram_bot_token("legacy-token")
    c.space.telegram_group_chat_id = "-123"
    c.space.save(update_fields=["telegram_bot_token", "telegram_group_chat_id"])
    bot_http.responses.append({"ok": True, "result": {"message_id": 1}})
    assert send_message(c.space, "room alert") is True
    req, _ = bot_http.calls[-1]
    assert req.full_url == "https://telegram.invalid/botlegacy-token/sendMessage"
    assert json.loads(req.data) == {"chat_id": "-123", "text": "room alert"}


def test_contract_token_is_shared_with_room_delivery(telegram_account, bot_http):
    c = telegram_account
    c.space.telegram_group_chat_id = "-123"
    bot_http.responses.append({"ok": True, "result": {"message_id": 1}})
    assert send_message(c.space, "room alert") is True
    assert bot_http.calls[-1][0].full_url == "https://telegram.invalid/bot12345:private-token/sendMessage"


@pytest.mark.parametrize("audience", ["requester", "staff", "member"])
def test_personal_body_cannot_fall_through_to_a_room(linked, bot_http, audience):
    linked.delivery.endpoint_id = None
    linked.delivery.envelope.audience = audience
    before = len(bot_http.calls)
    result = linked.provider.send(linked.delivery, {"text": "requester private body"})
    assert result.error_code == "invalid_endpoint"
    assert len(bot_http.calls) == before


def test_getme_timeout_is_not_an_ambiguous_send(bot_http):
    bot_http.responses.append(TimeoutError("private-token"))
    result, data = call("12345:private-token", "getMe", {})
    assert result.error_code == "timeout" and not result.ambiguous and data is None


@pytest.mark.parametrize("extra", [{"reply_markup": {"inline_keyboard": []}}, {"parse_mode": "HTML"}])
def test_transport_rejects_keyboard_or_parse_mode_even_from_internal_callers(telegram_environment, extra):
    result, _ = call("12345:private-token", "sendMessage", {"chat_id": "789", "text": "body", **extra})
    assert not result.accepted and result.error_code == "provider_error"
    telegram_environment.assert_not_called()
