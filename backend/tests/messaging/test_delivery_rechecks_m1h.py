"""Delivery-time rechecks on the canonical addressed pipeline (D1).

These replace the retired MessagingDelivery worker tests: every gate the old worker
re-read before provider I/O is re-read by ``notification_addressed`` before a send.
"""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from apps.accounts.models import User
from apps.integrations.messaging.consent import grant_consent
from apps.integrations.messaging.protections import recipient_hash, suppressed
from apps.integrations.messaging.stops import suppress_recipient
from apps.integrations.messaging.transport import SendResult
from apps.integrations.models import MessagingSuppression, NotificationPreference, PlatformSmsSettings
from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from apps.integrations.notification_addressed import eligible, send_sms, snapshot
from apps.integrations.notification_resolution import target_eligible
from apps.makerspaces.models import MakerspaceMembership
from tests.messaging.canonical_helpers import PLATFORM_SMS_KEY, envelope, platform_sms, sms_channel

pytestmark = pytest.mark.django_db


@pytest.fixture
def ready(space, member):
    """A consented member, an opted-in platform SMS sender and an enabled matrix cell."""
    platform_sms()
    config = sms_channel(space)
    NotificationPreference.objects.update_or_create(makerspace=space, feature="hardware_requests",
                                                    channel="sms", defaults={"enabled": True})
    grant_consent(user=member, makerspace_id=space.pk, channel="sms", action="opted_in")
    return SimpleNamespace(space=space, member=member, config=config)


def revoke(ctx, change):
    user, space = ctx.member, ctx.space
    if change == "consent":
        grant_consent(user=user, makerspace_id=space.pk, channel="sms", action="opted_out")
    elif change in {"membership", "receives"}:
        values = {"status": "revoked"} if change == "membership" else {"receives_notifications": False}
        MakerspaceMembership.objects.filter(user=user, makerspace=space).update(**values)
    elif change == "account":
        User.objects.filter(pk=user.pk).update(is_active=False)
    elif change == "phone":
        User.objects.filter(pk=user.pk).update(phone_verified_at=None)
    elif change == "module":
        space.enabled_modules = [key for key in space.enabled_modules if key != "sms"]
        space.save(update_fields=["enabled_modules"])
    elif change == "personal":
        from apps.notifications.models import MemberNotificationPreference
        MemberNotificationPreference.objects.create(makerspace=space, user=user,
            feature="hardware_requests", channel="sms", enabled=False)
    elif change == "sender":
        PlatformSmsSettings.objects.update(notifications_enabled=False)
    elif change == "channel":
        ctx.config.personal_enabled = False
        ctx.config.save(update_fields=["personal_enabled"])
    elif change == "suppressed":
        suppress_recipient("sms", PLATFORM_SMS_KEY, recipient_hash("phone", user.phone_e164))


@pytest.mark.parametrize("change", ["consent", "membership", "receives", "account", "phone", "module",
                                    "personal", "sender", "channel", "suppressed"])
def test_changes_after_enqueue_are_rechecked_at_delivery(ready, change):
    intent = envelope(ready.space, ready.member)
    assert eligible(intent, "sms")
    revoke(ready, change)
    assert not eligible(intent, "sms")


def test_matrix_cell_is_rechecked_at_delivery(ready):
    intent = envelope(ready.space, ready.member)
    assert target_eligible(intent, "sms")
    NotificationPreference.objects.filter(makerspace=ready.space, channel="sms").update(enabled=False)
    assert not target_eligible(intent, "sms")


def test_inbox_module_removal_does_not_disable_addressed_messaging(ready):
    ready.space.enabled_modules = [key for key in ready.space.enabled_modules if key != "notifications"]
    ready.space.save(update_fields=["enabled_modules"])
    assert eligible(envelope(ready.space, ready.member), "sms")


def test_stale_attempt_cannot_settle_and_acceptance_never_lowers_callback_progress(ready):
    from apps.integrations.notification_delivery import record_result
    from apps.integrations.notification_providers import ProviderResult
    stale = bound_leg(ready, "fenced")
    NotificationDelivery.objects.filter(pk=stale.pk).update(attempt_count=2)
    record_result(stale, ProviderResult(True, provider_id="SMstale"))
    stale.refresh_from_db()
    assert stale.state == "retrying" and stale.provider_id == ""
    early = bound_leg(ready, "early-read")
    NotificationDelivery.objects.filter(pk=early.pk).update(state="read", provider_id="SMearly")
    record_result(early, ProviderResult(True, provider_id="SMearly"))
    early.refresh_from_db()
    assert early.state == "read"


def bound_leg(ctx, key):
    intent = envelope(ctx.space, ctx.member, key=key)
    NotificationEnvelope.objects.filter(pk=intent.pk).update(routing_snapshot={"sms": snapshot(intent)})
    intent.refresh_from_db()
    return NotificationDelivery.objects.create(makerspace=ctx.space, envelope=intent, channel="sms",
        target_key="sms", provider="twilio", sender_key=PLATFORM_SMS_KEY, provider_source="platform",
        attempt_count=1, recipient_phone_hash=recipient_hash("phone", ctx.member.phone_e164))


@pytest.mark.parametrize("code,reason", [("21610", "provider_opt_out"), ("21211", "permanent_failure"),
                                         ("21614", "permanent_failure")])
def test_permanent_phone_errors_suppress_the_sender_recipient(ready, code, reason):
    row = bound_leg(ready, "permanent")
    with patch("apps.integrations.notification_resolution.eligible", return_value=True), patch(
            "apps.integrations.messaging.twilio.send_message", return_value=SendResult(error_code=code, permanent=True)) as send:
        result = send_sms(row)
    send.assert_called_once()
    assert not result.accepted and result.error_code == code
    phone = recipient_hash("phone", ready.member.phone_e164)
    assert MessagingSuppression.objects.get(sender_key=PLATFORM_SMS_KEY, recipient_hash=phone).reason == reason
    assert suppressed("sms", PLATFORM_SMS_KEY, phone)
    assert not eligible(envelope(ready.space, ready.member, key="next"), "sms")


def test_rotated_consent_or_sender_invalidates_a_queued_intent(ready):
    row = bound_leg(ready, "rotated")
    grant_consent(user=ready.member, makerspace_id=ready.space.pk, channel="sms", action="opted_in")
    with patch("apps.integrations.notification_resolution.eligible", return_value=True), patch(
            "apps.integrations.messaging.twilio.send_message") as send:
        result = send_sms(row)
    # The queued intent was bound to the older consent row; it cannot borrow the new one.
    assert result.error_code == "skipped"
    send.assert_not_called()


@pytest.mark.parametrize("operation", ["consent", "stop_annotation"])
def test_tenant_mutations_take_gate_before_whatsapp_sender(space, member, operation):
    from apps.integrations.messaging import consent, stops
    from apps.tenant_migration import gate_runtime
    from tests.messaging.canonical_helpers import (
        PLATFORM_WA_KEY, platform_whatsapp, verified_endpoint, whatsapp_channel,
    )
    platform_whatsapp()
    verified_endpoint(member, whatsapp_channel(space))
    if operation == "stop_annotation":
        grant_consent(user=member, makerspace_id=space.pk, channel="whatsapp", action="opted_in")
    checks = []
    validate = gate_runtime._assert_gate_state
    module = consent if operation == "consent" else stops
    sender_lock = module.lock_whatsapp_sender

    def gate(pk):
        validate(pk)
        checks.append("gate")

    def sender(key):
        assert "gate" in checks  # Tenant gate -> WhatsApp sender lock, never the reverse.
        checks.append("sender")
        sender_lock(key)

    with patch.object(gate_runtime, "_assert_gate_state", side_effect=gate), \
            patch.object(module, "lock_whatsapp_sender", side_effect=sender):
        if operation == "consent":
            consent.grant_consent(user=member, makerspace_id=space.pk, channel="whatsapp", action="opted_in")
        else:
            stops.append_stop_consents(SimpleNamespace(channel="whatsapp", sender_key=PLATFORM_WA_KEY,
                payload={"stop": True, "phone_hash": recipient_hash("phone", member.phone_e164)}))
    assert "sender" in checks
