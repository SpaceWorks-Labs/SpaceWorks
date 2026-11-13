from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.integrations.models_endpoints import NotificationEndpoint, NotificationEndpointChallenge
from apps.integrations.notification_proofs import start
from apps.integrations.notification_providers import provider_for

pytestmark = pytest.mark.django_db


def test_deep_link_getme_cached_per_generation(telegram_account, begin, bot_http):
    c = telegram_account
    _, code, result = begin()
    assert result == {"connect_url": f"https://t.me/SpaceWorksBot?start={code}"}
    assert len(bot_http.calls) == 1 and bot_http.calls[0][0].full_url.endswith("/getMe")
    NotificationEndpointChallenge.objects.update(created_at=timezone.now() - timedelta(minutes=2))
    start(c.user, c.config, "v1")
    assert len(bot_http.calls) == 1
    c.config.generation += 1
    c.config.save(update_fields=["generation"])
    NotificationEndpointChallenge.objects.update(created_at=timezone.now() - timedelta(minutes=2))
    begin()
    assert len(bot_http.calls) == 2


def test_private_start_binds_account_tenant_and_sender(telegram_account, begin, webhook):
    c = telegram_account
    challenge, code, _ = begin()
    assert webhook(code).status_code == 200
    endpoint = NotificationEndpoint.objects.get()
    assert (endpoint.user_id, endpoint.makerspace_id, endpoint.configuration_id) == (c.user.pk, c.space.pk, c.config.pk)
    assert endpoint.destination == endpoint.provider_subject == "789"
    assert endpoint.integration_generation == c.config.generation
    assert endpoint.integration_identity == c.config.integration_identity
    assert endpoint.verification_state == "verified" and endpoint.consented_at and endpoint.last_inbound_at
    challenge.refresh_from_db()
    assert challenge.consumed_at and challenge.endpoint_id == endpoint.pk
    assert AuditLog.objects.filter(action="notification.endpoint_verified").count() == 1


@pytest.mark.parametrize("failure", ["expired", "replay", "rotated", "disabled", "notifications_off", "telegram_off", "attempts"])
def test_stale_proof_never_creates_an_endpoint(telegram_account, begin, webhook, failure):
    c = telegram_account
    challenge, code, _ = begin()
    if failure == "expired":
        challenge.expires_at = timezone.now() - timedelta(seconds=1)
        challenge.save(update_fields=["expires_at"])
    elif failure == "replay":
        assert webhook(code).status_code == 200
    elif failure == "rotated":
        c.config.generation += 1
        c.config.save(update_fields=["generation"])
    elif failure == "disabled":
        c.config.personal_enabled = False
        c.config.save(update_fields=["personal_enabled"])
    elif failure == "attempts":
        challenge.attempts = 5
        challenge.save(update_fields=["attempts"])
    else:
        removed = "notifications" if failure == "notifications_off" else "telegram"
        c.space.enabled_modules = [key for key in c.space.enabled_modules if key != removed]
        c.space.save(update_fields=["enabled_modules"])
    assert webhook(code).status_code == 200
    assert NotificationEndpoint.objects.count() == (1 if failure == "replay" else 0)
    assert AuditLog.objects.filter(action="notification.endpoint_verified").count() == (1 if failure == "replay" else 0)


@pytest.mark.parametrize("mutation", ["group", "supergroup", "channel", "different_sender", "bot", "forwarded", "edited", "extra_text", "callback"])
def test_only_original_private_start_is_a_proof(begin, webhook, mutation):
    _, code, _ = begin()
    message = {"text": f"/start {code}", "chat": {"id": 789, "type": "private"}, "from": {"id": 789, "is_bot": False}}
    body = {"message": message}
    if mutation in {"group", "supergroup", "channel"}:
        message["chat"]["type"] = mutation
    elif mutation == "different_sender":
        message["from"]["id"] = 987
    elif mutation == "bot":
        message["from"]["is_bot"] = True
    elif mutation == "forwarded":
        message["forward_origin"] = {"type": "user"}
    elif mutation == "edited":
        body = {"edited_message": message}
    elif mutation == "extra_text":
        message["text"] += " trailing"
    else:
        body["callback_query"] = {"data": "accept:1", "from": {"id": 789}}
    assert webhook(body=body).status_code == 200
    assert not NotificationEndpoint.objects.exists()


@pytest.mark.parametrize("secret", ["", "wrong", "\N{SNOWMAN}"])
def test_secret_fails_closed_before_lookup(begin, webhook, secret):
    challenge, code, _ = begin()
    assert webhook(code, secret=secret).status_code == 403
    challenge.refresh_from_db()
    assert challenge.attempts == 0 and challenge.consumed_at is None


def test_unset_secret_fails_closed(begin, webhook, settings):
    _, code, _ = begin()
    settings.TELEGRAM_WEBHOOK_SECRET = ""
    assert webhook(code).status_code == 403
    assert not NotificationEndpoint.objects.exists()


@pytest.mark.parametrize("reply", [{"ok": False, "error_code": 401}, {"ok": True, "result": {}}, {"ok": True, "result": {"username": "../../wrong"}}])
def test_getme_failure_is_typed_without_raw_secrets(telegram_account, bot_http, reply):
    bot_http.responses.append(reply)
    with pytest.raises(ValidationError) as caught:
        start(telegram_account.user, telegram_account.config, "v1")
    assert "provider could not start verification" in str(caught.value)
    assert "private-token" not in str(caught.value)
    assert not NotificationEndpoint.objects.exists()


def test_browser_cannot_supply_a_destination_or_forge_a_proof(telegram_account, begin):
    c = telegram_account
    challenge, code, _ = begin()
    client = APIClient()
    client.force_authenticate(c.user)
    prefix = f"/api/v1/integrations/makerspace/{c.space.pk}/personal"
    response = client.post(prefix + "/endpoints/start", {"channel": "telegram", "consent": True,
        "consent_version": "v1", "destination": "789"}, format="json")
    assert response.status_code == 400
    response = client.post(prefix + f"/challenges/{challenge.pk}/verify", {"code": code}, format="json")
    assert response.status_code == 400
    assert not NotificationEndpoint.objects.exists()


def test_provider_is_registered_without_test_setup(telegram_account):
    from apps.integrations.notification_telegram import TelegramProvider
    assert isinstance(provider_for(telegram_account.config), TelegramProvider)
