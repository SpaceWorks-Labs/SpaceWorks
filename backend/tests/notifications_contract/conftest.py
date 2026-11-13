from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.integrations.models_endpoints import ChannelConfiguration, NotificationEndpoint
from apps.integrations.notification_fake import FakeProvider
from apps.integrations.notification_outbox import emit
from apps.integrations.notification_providers import PROVIDERS
from apps.integrations.notification_sources import NotificationSource, SOURCES
from apps.makerspaces.models import MakerspaceMembership
from apps.accounts.models import User
from tests.return_helpers import make_member, make_space


@pytest.fixture
def contract(monkeypatch):
    space = make_space("notification-contract")
    user = make_member("notify-owner", space, membership_role=MakerspaceMembership.Role.CUSTOM, role=User.Role.REQUESTER)
    membership = user.makerspace_memberships.get(makerspace=space)
    membership.assigned_role = space.roles.get(slug="member")
    membership.save(update_fields=["assigned_role"])
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])
    config = ChannelConfiguration.objects.create(makerspace=space, channel="telegram", provider="telegram",
        enabled=True, personal_enabled=True, integration_identity="bot-123")
    endpoint = NotificationEndpoint.objects.create(makerspace=space, user=user, configuration=config,
        channel="telegram", provider="telegram", destination="private-123", provider_subject="user-123",
        identity_digest="a" * 64, integration_identity=config.integration_identity,
        integration_generation=config.generation, verified_at=timezone.now(), consented_at=timezone.now(), consent_version="v1")
    fake = FakeProvider(config)
    monkeypatch.setitem(PROVIDERS, ("telegram", "telegram"), lambda _: fake)
    state = {"valid": True}
    monkeypatch.setitem(SOURCES, "contract.test", NotificationSource(lambda _: state["valid"]))
    monkeypatch.setattr("apps.integrations.notification_catalog.is_notification_enabled", lambda *args: True)
    def envelope(**kwargs):
        values = dict(makerspace=space, recipient=user, feature="hardware_requests", stream="hardware",
            event="accepted", audience="requester", source_kind="contract.test", source_id=1,
            dedup_key=f"contract:{kwargs.get('event', 'accepted')}", rendered={"subject": "Loan", "text": "Your loan changed."})
        values.update(kwargs)
        return emit(**values)
    return SimpleNamespace(space=space, user=user, config=config, endpoint=endpoint,
                           fake=fake, envelope=envelope, state=state)
