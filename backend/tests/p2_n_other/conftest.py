"""Real domain rows and an explicit fake personal provider; no HTTP or SMTP."""
from types import SimpleNamespace

import pytest
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.integrations.models import NotificationPreference as Matrix
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.models_endpoints import ChannelConfiguration, NotificationEndpoint
from apps.integrations.notification_fake import FakeProvider
from apps.integrations.notification_providers import PROVIDERS
from apps.makerspaces.models import MakerspaceMembership
from apps.notifications.models_preferences import NotificationPreference
from tests.return_helpers import make_space, make_user


@pytest.fixture
def lane(monkeypatch, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    space = make_space("p2-n-other")
    space.enabled_features = sorted(set(space.enabled_features or []) | {
        "membership.lifecycle_mail", "membership.auto_renew", "membership.broadcasts",
        "membership.vouching", "billing.reminders", "billing.documents",
    })
    space.save(update_fields=["enabled_features"])
    config = ChannelConfiguration.objects.create(makerspace=space, channel="telegram", provider="telegram",
        enabled=True, personal_enabled=True, room_enabled=False, integration_identity="p2-test-bot")
    fake = FakeProvider(config)
    monkeypatch.setitem(PROVIDERS, ("telegram", "telegram"), lambda _: fake)
    enqueued = []
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", enqueued.append)
    def no_network(*args, **kwargs):
        raise AssertionError("Tests must never use real HTTP")
    monkeypatch.setattr("requests.sessions.Session.request", no_network)
    features = ("members", "payments", "api_access", "devices", "stock")
    for feature in features:
        Matrix.objects.create(makerspace=space, feature=feature, channel="telegram", enabled=True)
    @transaction.atomic
    def account(name, role=None):
        user = make_user(name, access_status=User.AccessStatus.ACTIVE,
            account_kind="staff" if role and role != "member" else "member",
            staff_makerspace=space if role and role != "member" else None)
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
        if role:
            MakerspaceMembership.objects.create(makerspace=space, user=user, status="active",
                role="space_manager" if role == "space_manager" else "custom",
                assigned_role=space.roles.get(slug=role), activated_at=timezone.now())
        NotificationEndpoint.objects.create(makerspace=space, user=user, configuration=config,
            channel="telegram", provider="telegram", destination=f"private-{user.pk}",
            provider_subject=f"subject-{user.pk}", identity_digest=f"{user.pk:064x}",
            integration_identity=config.integration_identity, integration_generation=config.generation,
            verified_at=timezone.now(), consented_at=timezone.now(), consent_version="v1")
        for feature in features:
            NotificationPreference.objects.create(makerspace=space, user=user, category=feature,
                                                  channels=["telegram"], email_fallback=False)
        return user
    manager = account("p2-manager", "space_manager")
    owner = account("p2-owner", "member")
    membership = MakerspaceMembership.objects.get(makerspace=space, user=owner)
    membership.activated_by = manager
    membership.save(update_fields=["activated_by"])
    def deliver(event, recipient=owner):
        from apps.integrations.notification_tasks import deliver_envelope
        envelope = NotificationEnvelope.objects.get(makerspace=space, recipient=recipient, event=event)
        deliver_envelope(envelope.pk)
        return envelope
    return SimpleNamespace(space=space, manager=manager, owner=owner, membership=membership,
        config=config, fake=fake, account=account, enqueued=enqueued, deliver=deliver)


@pytest.fixture
def payment(lane):
    from apps.hardware_requests.models import HardwareRequest
    from apps.payments.models import Payment
    owner = lane.account("p2-account-only")
    request = HardwareRequest.objects.create(makerspace=lane.space, requester=owner,
        requester_username=owner.username, status="accepted")
    return Payment.objects.create(makerspace=lane.space, member=owner, subject_type="loan_deposit",
        subject_id=request.pk, amount="25.00", currency="usd", provider="unclaimed", created_by=lane.manager,
        due_at=timezone.now())
