from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.db import transaction
from django.utils import timezone

from apps.integrations.models_messaging_consent import MessagingConsent, MessagingRecipientCorrelation
from apps.integrations.messaging.consent import live_consent
from apps.integrations.messaging.correlation import claim_canonical_probe
from apps.integrations.messaging.locks import lock_whatsapp_sender
from apps.integrations.messaging.protections import recipient_hash
from apps.integrations.messaging.stops import process_stop
from apps.integrations.messaging.segments import prepare_sms
from apps.integrations.notification_sender import callback_configurations, preserve_configuration, sms_sender
from apps.integrations.notification_wa_window import in_session_window
from apps.integrations.notification_wa_meta_templates import document_header_approved
from .reconciliation_helpers import account, delivery, sms_config, space

pytestmark = pytest.mark.django_db


def test_sms_consent_binds_phone_verification_instance_and_sender_generation():
    tenant = space()
    user = account(phone_e164="+14155550123", phone_verified_at=timezone.now())
    config = sms_config(tenant)
    MessagingConsent.objects.create(makerspace=tenant, user=user, channel="sms", action="opted_in",
        source="member_settings", phone_e164=user.phone_e164, phone_verified_at=user.phone_verified_at,
        sender_key=config.sender_key, configuration_generation=config.generation)
    assert live_consent(tenant, user, "sms", configuration=config)
    user.phone_verified_at += timedelta(seconds=1)  # A -> B -> A with a new verification never revives it.
    assert not live_consent(tenant, user, "sms", configuration=config)
    user.phone_verified_at -= timedelta(seconds=1)
    config.generation += 1
    assert not live_consent(tenant, user, "sms", configuration=config)


def test_partial_own_sender_never_falls_back_to_platform(monkeypatch):
    config = sms_config(space())
    config.use_platform_sender = True
    config.set_credentials({"account_sid": "AC" + "a" * 32})
    config.save()
    calls = []
    monkeypatch.setattr("apps.integrations.messaging.resolver.resolve_sender", lambda *args: calls.append(args))
    assert sms_sender(config) is None
    assert calls == []


def test_platform_requires_explicit_tenant_opt_in(monkeypatch):
    config = sms_config(space())
    config.set_credentials({})
    monkeypatch.setattr("apps.integrations.messaging.resolver.resolve_sender", lambda *args: "platform")
    assert sms_sender(config) is None
    config.use_platform_sender = True
    assert sms_sender(config) == "platform"


def test_shared_sender_alias_stop_blocks_unknown_correlations_across_tenants():
    one, two = space(), space("recon-other")
    user = account()
    sender = "meta:waba:number"
    a = delivery(one, user, channel="whatsapp", sender_key=sender,
        recipient_phone_hash=recipient_hash("phone", "+14155550123"))
    b = delivery(two, user, channel="whatsapp", number=2, sender_key=sender,
        recipient_phone_hash=recipient_hash("phone", "+14155550124"))
    with transaction.atomic():
        lock_whatsapp_sender(sender)
        assert claim_canonical_probe(a) == "probe"
        assert claim_canonical_probe(b) == "probe"
        process_stop(SimpleNamespace(channel="whatsapp", sender_key=sender,
            payload={"stop": True, "alias_hash": recipient_hash("alias", "bsuid"), "phone_hash": ""}))
    assert MessagingRecipientCorrelation.objects.filter(sender_key=sender, state="blocked").count() == 2
    with transaction.atomic():
        lock_whatsapp_sender(sender)
        assert claim_canonical_probe(a) == "blocked"


@pytest.mark.parametrize("text", ["^" * 500, "😀" * 300, "A" * 600])
def test_sms_truncation_recounts_extensions_and_utf16_without_exceeding_cap(text):
    result = prepare_sms(text)
    assert result.estimated_segments <= 3
    assert result.body.endswith("...")


def test_whatsapp_window_is_strict_at_24_hours_and_refuses_future():
    now = timezone.now()
    for moment, expected in [(now - timedelta(hours=24), False), (now + timedelta(seconds=1), False),
                             (now - timedelta(hours=23), True)]:
        assert in_session_window(SimpleNamespace(last_inbound_at=moment), now=now) is expected


@pytest.mark.parametrize("provider_template,expected", [
    ({"components": [{"type": "BODY", "text": "Booking {{1}}"}]}, True),
    ({"components": [{"type": "BODY", "text": "Booking {{name}}"}]}, False),
    ({"parameter_format": "NAMED", "components": [{"type": "BODY", "text": "Booking {{1}}"}]}, False),
    ({"components": [{"type": "BODY", "text": "Booking {{1}}"}, {"type": "BUTTONS", "buttons": []}]}, False),
])
def test_meta_approval_requires_exact_reviewed_positional_body(provider_template, expected):
    binding = SimpleNamespace(variables=["booking.id"], feature="bookings")
    assert document_header_approved(binding, provider_template) is expected


def test_account_only_event_owner_has_a_tie_but_revocation_wins():
    from apps.events.models import Event, EventRegistration
    from apps.makerspaces.models import MakerspaceMembership
    from apps.integrations.messaging.ties import has_tenant_tie
    tenant, other = space(), space("foreign")
    user = account()
    now = timezone.now()
    event = Event.objects.create(makerspace=tenant, title="Workshop", starts_at=now,
        ends_at=now + timedelta(hours=1), status="published", registration_audience="accounts")
    assert not has_tenant_tie(user, tenant)
    EventRegistration.objects.create(event=event, member=user, name="Member", email=user.email, phone="")
    assert has_tenant_tie(user, tenant)
    assert not has_tenant_tie(user, other)
    membership = MakerspaceMembership.objects.create(makerspace=tenant, user=user, role="custom",
        assigned_role=tenant.roles.get(slug="member"), status="revoked")
    assert not has_tenant_tie(user, tenant)
    membership.status = "active"
    membership.save(update_fields=["status"])
    assert has_tenant_tie(user, tenant)
    user.access_status = "restricted"
    user.save(update_fields=["access_status"])
    assert not has_tenant_tie(user, tenant)


def test_shared_contact_staff_account_does_not_inherit_member_tie():
    from apps.makerspaces.models import MakerspaceMembership
    from apps.integrations.messaging.ties import has_tenant_tie
    tenant = space()
    user = account(phone_e164="+14155550123", phone_verified_at=timezone.now())
    # A valid staff principal (exactly one fixed-tenant membership) sharing contacts.
    from tests.fixed_roles.helpers import staff_account
    staff = staff_account(tenant, "recon-staff", "space_manager",
        phone_e164=user.phone_e164, phone_verified_at=user.phone_verified_at)
    MakerspaceMembership.objects.create(makerspace=tenant, user=user, role="custom",
        assigned_role=tenant.roles.get(slug="member"))
    assert has_tenant_tie(user, tenant)
    assert not has_tenant_tie(staff, tenant)


def test_addressed_quota_is_reserved_once_and_local_refusal_spends_nothing(monkeypatch):
    from unittest.mock import Mock
    from apps.integrations.notification_quotas import reserve
    tenant, user = space(), account()
    config = sms_config(tenant)
    config.quotas = {"daily_limit": 1}
    config.save(update_fields=["quotas"])
    row = delivery(tenant, user)
    counter = Mock(return_value=True)
    monkeypatch.setattr("apps.makerspaces.limits.reserve_notification_quota", counter)
    assert reserve(row) and reserve(row)
    counter.assert_called_once()
    another = delivery(tenant, user, number=2)
    assert not reserve(another)
    counter.assert_called_once()


def test_legacy_room_fanout_cannot_enqueue_duplicate_addressed_work(monkeypatch):
    from unittest.mock import Mock
    from apps.integrations.notify import LifecyclePayload, _run_guarded
    from apps.integrations.models_messaging_delivery import MessagingDelivery
    legacy = Mock(side_effect=AssertionError("Duplicate addressed producer"))
    monkeypatch.setattr("apps.integrations.messaging.dispatch.enqueue_addressed_messages", legacy)
    monkeypatch.setattr("apps.integrations.notify.is_notification_enabled", lambda *args: False)
    _run_guarded(space(), "bookings", "confirmed", lambda: LifecyclePayload(text="Staff summary"), True)
    legacy.assert_not_called()
    assert not MessagingDelivery.objects.exists()


def test_old_sms_intent_cannot_acquire_a_later_consent():
    from apps.integrations.notification_addressed import snapshot, binding_current
    tenant = space()
    user = account(phone_e164="+14155550123", phone_verified_at=timezone.now())
    config = sms_config(tenant)
    candidate = SimpleNamespace(makerspace=tenant, recipient=user, routing_snapshot={})
    assert snapshot(candidate) is None
    values = dict(makerspace=tenant, user=user, channel="sms", action="opted_in", source="member_settings",
        phone_e164=user.phone_e164, phone_verified_at=user.phone_verified_at, sender_key=config.sender_key,
        configuration_generation=config.generation)
    MessagingConsent.objects.create(**values)
    candidate.routing_snapshot["sms"] = snapshot(candidate)
    assert binding_current(candidate, config, sms_sender(config))
    MessagingConsent.objects.create(**values)
    assert not binding_current(candidate, config, sms_sender(config))


def test_removing_optional_inbox_cannot_erase_retained_personal_opt_outs(monkeypatch):
    from django.apps import apps
    from apps.integrations import notification_personal_policy as policy
    tenant, user = space(), account()
    apps.get_model("notifications", "MemberNotificationPreference").objects.create(
        makerspace=tenant, user=user, feature="bookings", channel="sms", enabled=False)
    apps.get_model("notifications", "NotificationPreference").objects.create(
        makerspace=tenant, user=user, category="bookings", channels=[], email_fallback=False)
    monkeypatch.setattr(policy.apps, "is_installed", lambda name: False)
    monkeypatch.setattr(policy, "selection_model", lambda: None)
    assert not policy.personal_enabled(tenant, user.pk, "bookings", "sms")
    retained = policy.preference_for(tenant, user, "bookings")
    assert retained.channels == [] and not retained.email_fallback
    assert policy.personal_enabled(tenant, user.pk, "events", "sms")  # No positive consent is inferred.


def test_delayed_old_proof_cannot_lift_a_newer_alias_stop():
    from apps.integrations.models_endpoints import ChannelConfiguration, NotificationEndpoint
    from apps.integrations.notification_whatsapp_consent import proof_receipt, record_proof_consent
    from apps.integrations.messaging.stops import suppress_recipient
    from apps.integrations.models_messaging_consent import MessagingSuppression
    tenant, user = space(), account()
    config = ChannelConfiguration.objects.create(makerspace=tenant, channel="whatsapp", provider="meta",
        integration_identity="phone-id", sender_key="meta:waba:phone-id", enabled=True, personal_enabled=True)
    endpoint = NotificationEndpoint.objects.create(makerspace=tenant, user=user, channel="whatsapp", provider="meta",
        configuration=config, integration_identity=config.integration_identity, integration_generation=config.generation,
        identity_digest="a" * 64, destination="+14155550123", provider_subject="+14155550123",
        verified_at=timezone.now(), consented_at=timezone.now(), consent_version="v1")
    older = timezone.now() - timedelta(minutes=1)
    with transaction.atomic():
        lock_whatsapp_sender(config.sender_key)
        suppress_recipient("whatsapp", config.sender_key, recipient_hash("alias", "new-stop"), kind="alias")
        with proof_receipt(older):
            record_proof_consent(config, endpoint)
    assert MessagingRecipientCorrelation.objects.get().state == "blocked"
    assert MessagingSuppression.objects.get().lifted_at is None
    with transaction.atomic():
        lock_whatsapp_sender(config.sender_key)
        with proof_receipt(timezone.now()):
            record_proof_consent(config, endpoint)
    assert not MessagingRecipientCorrelation.objects.exists()
    assert MessagingSuppression.objects.get().lifted_at is None  # Never lift another unknown destination's alias.
