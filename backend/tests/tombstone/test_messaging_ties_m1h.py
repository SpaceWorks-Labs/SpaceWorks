"""Run only under tests/tombstone's real import-time tombstone profile.

Account-only tenant ties (ownership, no membership) still admit consent and canonical
addressed delivery when the optional ``notifications`` app is tombstoned.
"""
import pytest
from django.utils import timezone

from tests.tombstone.canonical_sms import canonical_sms_leg, send_accepted


@pytest.mark.django_db
def test_account_only_ties_consent_and_delivery_without_notifications(monkeypatch, settings):
    from apps.accounts.models import User
    from apps.hardware_requests.models import HardwareRequest
    from apps.integrations.messaging.consent import grant_consent, live_consent, member_space
    from apps.integrations.messaging.ties import has_tenant_tie
    from apps.integrations.models import NotificationPreference
    from apps.integrations.notification_addressed import eligible
    from apps.makerspaces.models import Makerspace
    from apps.separability.registry import runtime_active
    from tests.messaging.canonical_helpers import envelope, platform_sms, sms_channel

    assert not runtime_active("notifications")
    settings.MESSAGING_WEBHOOK_BASE_URL = "https://api.example.test"
    space = Makerspace.objects.create(name="Account-only tombstone", slug="tombstone-ties")
    user = User.objects.create_user(username="tombstone-ties", phone_e164="+14155552671",
                                    phone_verified_at=timezone.now())
    platform_sms()
    sms_channel(space)
    NotificationPreference.objects.update_or_create(makerspace=space, feature="hardware_requests",
                                                    channel="sms", defaults={"enabled": True})
    # Before any ownership there is no tie, so neither consent nor delivery is admitted.
    assert not has_tenant_tie(user, space)
    assert not eligible(envelope(space, user, key="tombstone-tie-before"), "sms")
    HardwareRequest.objects.create(makerspace=space, requester=user, requester_username=user.username)

    assert not user.makerspace_memberships.exists()
    assert has_tenant_tie(user, space)
    assert member_space(user, space.pk) == space
    grant_consent(user=user, makerspace_id=space.pk, channel="sms", action="opted_in")
    assert live_consent(space, user, "sms")
    assert eligible(envelope(space, user, key="tombstone-tie-after"), "sms")
    leg = send_accepted(canonical_sms_leg(space, user, key="tombstone-tie", monkeypatch=monkeypatch), "SMties")
    assert leg.state == "accepted", leg.last_error

    # A tie lost after enqueue is rechecked at delivery: the leg is skipped, never sent.
    HardwareRequest.objects.filter(makerspace=space, requester=user).delete()
    assert not has_tenant_tie(user, space)
    from unittest.mock import patch
    from apps.integrations.notification_delivery import send
    later = canonical_sms_leg(space, user, key="tombstone-tie-lost", monkeypatch=monkeypatch)
    with patch("apps.integrations.messaging.twilio.send_message") as provider:
        send(later.pk)
    provider.assert_not_called()
    later.refresh_from_db()
    assert later.state == "skipped"
