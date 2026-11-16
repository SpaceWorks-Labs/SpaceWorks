from types import SimpleNamespace as Bag

import pytest
from django.utils import timezone

from apps.integrations.models_endpoints import NotificationEndpoint
from apps.integrations.notification_resolution import selected_policy
from apps.notifications.models_preferences import NotificationPreference
from tests.p3_review6.test_preferences import endpoint, selection

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("manager", [False, True])
def test_presence_defaults_precede_expiry_and_survive_another_category_save(world, monkeypatch, manager):
    user = world.staff if manager else world.owner
    if manager:
        config = world.config("telegram")
        NotificationEndpoint.objects.create(makerspace=world.space, user=user, configuration=config,
            channel="telegram", provider="telegram", destination="private-1", provider_subject="staff-1",
            identity_digest="f" * 64, integration_identity=config.integration_identity,
            integration_generation=config.generation, verified_at=timezone.now(), consented_at=timezone.now(),
            consent_version="v1")
    monkeypatch.setattr("apps.integrations.notification_availability.available_channels",
                        lambda _space, category: ["in_app", "native_push"] if category == "presence" else ["email"])
    envelope = Bag(makerspace=world.space, recipient=user, makerspace_id=world.space.pk,
                   recipient_id=user.pk, feature="presence")
    assert selected_policy(envelope) == (["in_app", "native_push"], False)
    envelope.feature = "hardware_requests"
    assert selected_policy(envelope) == (["telegram"] if manager else ["email", "in_app"], True)
    envelope.feature = "presence"
    client = world.client(user)
    for response in (client.get(endpoint(world)), client.put(endpoint(world), {"preferences": [
        {"category": "hardware_requests", "channels": ["email"], "email_fallback": True},
    ]}, format="json")):
        row = selection(response, "presence")
        assert row["channels"] == ["in_app", "native_push"] and not row["email_fallback"]
    assert not NotificationPreference.objects.filter(makerspace=world.space, user=user, category="presence").exists()


@pytest.mark.parametrize("channels", [[], ["in_app"]])
@pytest.mark.parametrize("fallback", [False, True])
def test_expiry_does_not_write_preferences_and_honors_explicit_choices(world, monkeypatch, channels, fallback):
    from apps.presence import notifications
    preference = NotificationPreference.objects.create(makerspace=world.space, user=world.owner,
        category="presence", channels=channels, email_fallback=fallback)
    captured = []
    monkeypatch.setattr(notifications, "emit", lambda **kwargs: captured.append(kwargs))
    row = Bag(pk=3, makerspace=world.space, account=world.owner, revision=1)
    notifications.remind(row)
    assert captured[0]["feature"] == "presence"
    preference.refresh_from_db()
    assert preference.channels == channels
    envelope = Bag(makerspace=world.space, recipient=world.owner, feature="presence")
    assert selected_policy(envelope) == (channels, fallback)
    preference.delete()
    notifications.remind(row)
    assert not NotificationPreference.objects.filter(makerspace=world.space, user=world.owner).exists()
    assert selected_policy(envelope) == (["in_app", "native_push"], False)
