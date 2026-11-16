"""Run with the real tombstone profile, whose conftest enforces import-time settings.

The retired MessagingDelivery worker is inert; the addressed SMS leg now travels the
canonical envelope pipeline. Tombstoning the optional ``notifications`` app removes its
runtime surfaces, never consented SMS: the leg is claimed, rechecked and accepted.
"""
import pytest
from django.utils import timezone

from tests.tombstone.canonical_sms import canonical_sms_leg, send_accepted


@pytest.mark.django_db
def test_canonical_sms_leg_survives_tombstoned_notifications(monkeypatch, settings):
    settings.MESSAGING_WEBHOOK_BASE_URL = "https://api.example.test"
    from apps.accounts.models import User
    from apps.integrations.messaging.consent import grant_consent
    from apps.integrations.models import NotificationPreference
    from apps.makerspaces.models import Makerspace
    from apps.notifications.models_inbox import NotificationInboxRow
    from apps.separability.registry import runtime_active
    from tests.fixed_roles.helpers import assign_builtin_roles
    from tests.messaging.canonical_helpers import platform_sms, sms_channel

    assert not runtime_active("notifications")
    space = Makerspace.objects.create(name="Tombstoned inbox", slug="tombstone-messaging")
    user = User.objects.create_user(username="tombstone-messaging", phone_e164="+14155552671",
                                    phone_verified_at=timezone.now())
    assign_builtin_roles(user, space, "member")
    platform_sms()
    sms_channel(space)
    NotificationPreference.objects.update_or_create(makerspace=space, feature="hardware_requests",
                                                    channel="sms", defaults={"enabled": True})
    grant_consent(user=user, makerspace_id=space.pk, channel="sms", action="opted_in")
    leg = send_accepted(canonical_sms_leg(space, user, key="tombstone-edge", monkeypatch=monkeypatch),
                        "SMtombstone")
    assert leg.state == "accepted", leg.last_error
    assert leg.provider_id == "SMtombstone" and leg.quota_reserved_at is not None
    # The tombstoned inbox wrote nothing; addressed delivery did not depend on it.
    assert not NotificationInboxRow.objects.exists()
