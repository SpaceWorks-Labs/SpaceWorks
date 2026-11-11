from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient

from apps.integrations.models_endpoints import NotificationEndpoint
from apps.integrations.notification_providers import provider_for
from apps.integrations.notification_resolution import endpoint_eligible, selected_policy
from tests.accounts.reauth_helpers import reauthenticate

pytestmark = pytest.mark.django_db


def test_manager_defaults_to_verified_telegram_then_email(telegram_account, begin, webhook):
    c = telegram_account
    envelope = SimpleNamespace(makerspace=c.space, makerspace_id=c.space.pk, recipient=c.user,
        recipient_id=c.user.pk, feature="hardware_requests")
    assert selected_policy(envelope)[0] == ["email"]
    _, code, _ = begin()
    assert webhook(code).status_code == 200
    assert selected_policy(envelope)[0] == ["telegram"]
    c.config.personal_enabled = False
    c.config.save(update_fields=["personal_enabled"])
    assert selected_policy(envelope)[0] == ["email"]


def test_token_rotation_via_frozen_api_advances_generation(telegram_account, begin, webhook, bot_http):
    c = telegram_account
    _, code, _ = begin()
    assert webhook(code).status_code == 200
    endpoint = NotificationEndpoint.objects.get()
    generation = c.config.generation
    client = APIClient()
    reauthenticate(client, c.user)  # Credential rotation is a step-up write.
    response = client.patch(f"/api/v1/integrations/makerspace/{c.space.pk}/channels/telegram",
        {"credentials": {"bot_token": "67890:rotated-token"}}, format="json")
    assert response.status_code == 200
    c.config.refresh_from_db()
    assert c.config.generation == generation + 1
    envelope = SimpleNamespace(makerspace=c.space, makerspace_id=c.space.pk, recipient_id=c.user.pk)
    assert not endpoint_eligible(endpoint, envelope)
    before = len(bot_http.calls)
    assert provider_for(c.config).test(endpoint).error_code == "invalid_endpoint"
    assert len(bot_http.calls) == before


def test_closed_tenant_gate_acknowledges_without_consuming(telegram_account, begin, webhook, monkeypatch):
    from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
    c = telegram_account
    challenge, code, _ = begin()

    def closed(*args, **kwargs):
        raise SourceMigrationGateClosed("Tenant frozen")

    monkeypatch.setattr("apps.tenant_migration.gate_runtime.assert_write_allowed", closed)
    assert webhook(code).status_code == 200
    challenge.refresh_from_db()
    assert challenge.consumed_at is None
    assert not NotificationEndpoint.objects.exists()


def test_same_telegram_identity_requires_each_accounts_own_proof(telegram_account, begin, webhook, bot_http):
    from django.utils import timezone
    from datetime import timedelta
    from apps.integrations.notification_proofs import start
    from apps.integrations.models_endpoints import NotificationEndpointChallenge
    from tests.return_helpers import make_member
    from urllib.parse import urlsplit, parse_qs
    c = telegram_account
    _, code, _ = begin()
    assert webhook(code).status_code == 200
    original = NotificationEndpoint.objects.get(user=c.user)
    other = make_member("telegram-other", c.space)
    NotificationEndpointChallenge.objects.update(created_at=timezone.now() - timedelta(minutes=2))
    _, result = start(other, c.config, "v1")
    other_code = parse_qs(urlsplit(result["connect_url"]).query)["start"][0]
    assert NotificationEndpoint.objects.filter(user=other).count() == 0
    assert webhook(other_code).status_code == 200
    original.refresh_from_db()
    linked = NotificationEndpoint.objects.get(user=other)
    assert NotificationEndpoint.objects.count() == 2
    assert original.user_id == c.user.pk and original.revoked_at is None
    assert linked.pk != original.pk and linked.user_id == other.pk
    assert linked.identity_digest == original.identity_digest
    # Replaying that proof cannot reassign or duplicate either account binding.
    assert webhook(other_code).status_code == 200
    assert NotificationEndpoint.objects.count() == 2
