from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.integrations.models_endpoints import ChannelConfiguration, NotificationEndpoint
from apps.integrations.notification_fake import FakeProvider
from apps.integrations.notification_providers import PROVIDERS
from apps.integrations.notification_sources import render
from apps.makerspaces.models import MakerspaceMembership
from apps.notifications.models_preferences import NotificationPreference
from tests.return_helpers import make_member, make_space, make_user


@pytest.fixture
def equipment(monkeypatch):
    space = make_space("p2-equipment")
    space.enabled_modules = sorted(set(space.enabled_modules) | {
        "machines", "machine_service", "printing", "maintenance", "procurement", "notifications",
        "membership", "email", "telegram", "public_inventory", "request_workflow",
    })
    space.enabled_features = sorted(set(space.enabled_features) | {
        "inventory.notify_when_back", "notifications.member_inbox", "machines.certifications",
    })
    space.save(update_fields=["enabled_modules", "enabled_features"])
    manager = make_member("p2-manager", space)
    owner = make_user("p2-owner", access_status="active")
    for user in (owner, manager):
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
    config = ChannelConfiguration.objects.create(makerspace=space, channel="telegram", provider="telegram",
        enabled=True, personal_enabled=True, integration_identity="p2-bot")
    fake = FakeProvider(config)
    monkeypatch.setitem(PROVIDERS, ("telegram", "telegram"), lambda _: fake)
    for user in (owner, manager):
        NotificationEndpoint.objects.create(makerspace=space, user=user, configuration=config,
            channel="telegram", provider="telegram", destination=f"private-{user.pk}",
            provider_subject=f"user-{user.pk}", identity_digest=f"{user.pk:064x}",
            verification_state="verified", integration_identity=config.integration_identity,
            integration_generation=config.generation, verified_at=timezone.now(), consented_at=timezone.now(), consent_version="v1")
        for category in ("hardware_requests", "printing", "maintenance", "certifications", "stock", "payments"):
            NotificationPreference.objects.create(makerspace=space, user=user, category=category,
                channels=["telegram"], email_fallback=False)
    monkeypatch.setattr("apps.integrations.notification_catalog.is_notification_enabled", lambda *args: True)
    monkeypatch.setattr("apps.hardware_requests.notifications_p2_rooms.is_notification_enabled", lambda *args: True)
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda *args: None)
    monkeypatch.setattr("apps.integrations.dispatch_channels._enqueue_notification", lambda *args: None)
    # No real SMTP, push or room provider is invoked by these tests.
    sent = []
    from apps.integrations.notification_providers import ProviderResult
    monkeypatch.setattr("apps.integrations.notification_builtin.send_builtin",
                        lambda delivery, body: sent.append((delivery.channel, body)) or ProviderResult(True))
    return SimpleNamespace(space=space, manager=manager, owner=owner, fake=fake, sent=sent, render=render)


def member_owner(world):
    return MakerspaceMembership.objects.create(makerspace=world.space, user=world.owner,
        role=MakerspaceMembership.Role.CUSTOM, assigned_role=world.space.roles.get(slug="member"))
