"""WhatsApp BSUID correlation barrier on canonical deliveries (D1).

A sender/phone may expose only one logical probe before verified identity
correlation, across tenants sharing a platform sender. The retired worker's probe
logic now lives in ``claim_canonical_probe`` / ``prepare_whatsapp`` /
``record_result`` / ``confirm_canonical_probe``; these tests drive those seams.
"""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.db import transaction
from django.utils import timezone

from apps.integrations.messaging.consent import grant_consent
from apps.integrations.messaging.correlation import confirm_canonical_probe
from apps.integrations.messaging.locks import lock_whatsapp_sender
from apps.integrations.messaging.protections import recipient_hash, suppressed
from apps.integrations.messaging.stops import process_stop
from apps.integrations.models import MessagingRecipientCorrelation
from apps.integrations.models_contract import NotificationDelivery
from apps.integrations.notification_addressed import prepare_whatsapp
from apps.integrations.notification_delivery import claim, record_result
from apps.integrations.notification_providers import ProviderResult
from apps.makerspaces.models import Makerspace
from tests.fixed_roles.helpers import assign_builtin_roles
from tests.messaging.canonical_helpers import (
    PLATFORM_WA_KEY, envelope, platform_whatsapp, verified_endpoint, whatsapp_channel,
)

pytestmark = pytest.mark.django_db
SENDER = PLATFORM_WA_KEY


def wa_leg(space, user, key, **values):
    """A claimed (attempt 1) WhatsApp leg addressed to the user's phone on the shared sender."""
    intent = envelope(space, user, key=key, source_kind="migration.history")
    return NotificationDelivery.objects.create(makerspace=space, envelope=intent, channel="whatsapp",
        target_key="whatsapp", provider="meta", sender_key=SENDER, attempt_count=1,
        recipient_phone_hash=recipient_hash("phone", user.phone_e164), **values)


def stop(alias="bsuid-one"):
    with transaction.atomic():
        lock_whatsapp_sender(SENDER)
        process_stop(SimpleNamespace(channel="whatsapp", sender_key=SENDER,
            payload={"stop": True, "alias_hash": recipient_hash("alias", alias)}))


def confirm(row, *, alias="", phone=None):
    with transaction.atomic():
        lock_whatsapp_sender(SENDER)
        confirm_canonical_probe(row, alias_hash=recipient_hash("alias", alias) if alias else "",
                                phone_hash=phone or "")


def held_back(row):
    """The leg was not submitted; returns its persisted state."""
    assert prepare_whatsapp(row) is False
    row.refresh_from_db()
    return row


def test_two_deliveries_before_callback_only_one_probe_and_no_wait_attempt(space, member):
    first, second = wa_leg(space, member, "first"), wa_leg(space, member, "second")
    assert prepare_whatsapp(first) is True
    second = held_back(second)
    # Waiting defers without spending an attempt.
    assert second.state == "retrying" and second.retryable and second.attempt_count == 0
    assert second.next_attempt_at > timezone.now() and second.claim_until is None
    assert MessagingRecipientCorrelation.objects.get().probe_notification_delivery_id == first.pk


def test_bsuid_stop_without_context_probe_then_every_later_delivery_suppressed(space, member):
    stop()
    first = wa_leg(space, member, "first")
    assert prepare_whatsapp(first) is True
    confirm(first, alias="bsuid-one")
    correlation = MessagingRecipientCorrelation.objects.get()
    assert correlation.state == "confirmed" and correlation.alias_known
    # The verified alias now maps the earlier BSUID STOP onto this phone.
    assert suppressed("whatsapp", SENDER, recipient_hash("phone", member.phone_e164))


def test_missing_probe_callback_expires_waiting_delivery_after_72h(space, member):
    assert prepare_whatsapp(wa_leg(space, member, "first")) is True
    MessagingRecipientCorrelation.objects.update(probe_started_at=timezone.now() - timedelta(hours=73))
    waiting = held_back(wa_leg(space, member, "waiting"))
    assert (waiting.state, waiting.last_error, waiting.retryable) == ("skipped", "identity_unconfirmed", False)


def test_ambiguous_probe_never_resubmitted_and_late_opaque_callback_confirms(space, member):
    first = wa_leg(space, member, "first")
    assert prepare_whatsapp(first) is True
    record_result(first, ProviderResult(False, error_code="ambiguous_timeout", ambiguous=True, retryable=True))
    first.refresh_from_db()
    assert first.state == "held" and not first.retryable and first.provider_id == ""
    assert claim(first.pk) is None  # A held probe is never claimed again.
    assert held_back(first).state == "held"  # Re-entry cannot resubmit it either.
    assert MessagingRecipientCorrelation.objects.get().state == "probing"
    assert held_back(wa_leg(space, member, "waiting")).state == "retrying"
    confirm(first, alias="known")
    assert MessagingRecipientCorrelation.objects.get().state == "confirmed"


def test_definitive_probe_rejection_releases_phone_for_a_later_probe(space, member):
    first = wa_leg(space, member, "first")
    assert prepare_whatsapp(first) is True
    record_result(first, ProviderResult(False, error_code="130429", retryable=True))
    first.refresh_from_db()
    assert first.state == "retrying" and first.retryable
    assert not MessagingRecipientCorrelation.objects.exists()
    second = wa_leg(space, member, "after-repair")
    assert prepare_whatsapp(second) is True
    assert MessagingRecipientCorrelation.objects.get().probe_notification_delivery_id == second.pk


def test_early_provider_evidence_prevents_rejection_from_releasing_probe(space, member):
    first = wa_leg(space, member, "first")
    assert prepare_whatsapp(first) is True
    # A verified callback already proved the provider took this request.
    NotificationDelivery.objects.filter(pk=first.pk).update(provider_id="wamid.early", state="failed", retryable=False)
    record_result(first, ProviderResult(False, error_code="190"))
    assert MessagingRecipientCorrelation.objects.get().probe_notification_delivery_id == first.pk


def test_failed_probe_without_bsuid_cannot_open_with_unmapped_stop(space, member):
    stop()
    first = wa_leg(space, member, "first")
    assert prepare_whatsapp(first) is True
    phone = recipient_hash("phone", member.phone_e164)
    confirm(first, phone=phone)  # Phone-only evidence cannot open with an unmapped STOP.
    assert MessagingRecipientCorrelation.objects.get().state == "probing"
    assert held_back(wa_leg(space, member, "waiting")).state == "retrying"
    confirm(first, alias="bsuid-one", phone=phone)
    assert MessagingRecipientCorrelation.objects.get().state == "confirmed"
    assert suppressed("whatsapp", SENDER, phone)


def test_unmapped_stop_blocks_alias_unknown_confirmation_until_reconsent(space, member):
    platform_whatsapp()
    verified_endpoint(member, whatsapp_channel(space))
    first = wa_leg(space, member, "first")
    assert prepare_whatsapp(first) is True
    confirm(first, phone=recipient_hash("phone", member.phone_e164))
    correlation = MessagingRecipientCorrelation.objects.get()
    assert correlation.state == "confirmed" and correlation.alias_known is False
    stop()
    correlation.refresh_from_db()
    assert correlation.state == "blocked"
    waiting = held_back(wa_leg(space, member, "waiting"))
    assert (waiting.state, waiting.last_error) == ("skipped", "identity_unconfirmed")
    grant_consent(user=member, makerspace_id=space.pk, channel="whatsapp", action="opted_in")
    assert not MessagingRecipientCorrelation.objects.exists()


@pytest.mark.parametrize("purge_first", [False, True])
def test_two_tenants_share_platform_sender_barrier(space, member, purge_first):
    platform_whatsapp()
    whatsapp_channel(space)
    other = Makerspace.objects.create(name="Second tenant", slug="second-tenant")
    assign_builtin_roles(member, other, "member")
    first, second = wa_leg(space, member, "first"), wa_leg(other, member, "other")
    assert prepare_whatsapp(first) is True
    if purge_first:
        from apps.integrations.messaging.purge import purge_channel
        purge_channel(space, "whatsapp")  # Shared probe barriers survive tenant purge.
    assert held_back(second).state == "retrying"
    assert MessagingRecipientCorrelation.objects.count() == 1


def test_later_phone_only_callback_never_forgets_known_alias(space, member):
    first = wa_leg(space, member, "first")
    assert prepare_whatsapp(first) is True
    confirm(first, alias="known-alias")
    confirm(first, phone=recipient_hash("phone", member.phone_e164))
    assert MessagingRecipientCorrelation.objects.get().alias_known is True
