"""Pin decision 515's accepted 0.12.0 reserved-email-leg limitation.

These are boundary/constraint proofs, not a claim of implemented leg recovery.
"""
from unittest.mock import patch

import pytest
from django.db import IntegrityError, transaction

from apps.integrations.delivery_sources import prepare
from apps.integrations.models import EmailLog
from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from apps.integrations.notification_delivery import send
from apps.integrations.notification_tasks import deliver_envelope
from tests.billing_docs.test_email_recovery import set_switch
from tests.billing_docs.test_r2_email import document_ledger_snapshot, issue_mail

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("switch", ["email", "billing.documents"])
@pytest.mark.parametrize("boundary", ["resolution", "smtp_prepare"])
def test_reserved_document_leg_skip_is_terminal_and_unique_channel_blocks_fresh_attempt(
        document, document_mail, lane, switch, boundary, django_capture_on_commit_callbacks, mailoutbox):
    original = document_ledger_snapshot(document)
    if boundary == "resolution":
        with patch("apps.integrations.notification_delivery.send"):
            envelope = issue_mail(document, "envelope", django_capture_on_commit_callbacks, document_mail)
        delivery = envelope.deliveries.get(channel="email")
        assert (delivery.state, delivery.attempt_count) == ("retrying", 0)
        set_switch(lane.space, switch, False)
        send(delivery.pk)
        expected_error = "live_eligibility_changed"
        assert EmailLog.objects.filter(event="document_issued").count() == 0
    else:
        def disable_after_prepare(log):
            assert prepare(log) is True
            set_switch(lane.space, switch, False)
            return True

        with patch("apps.integrations.delivery_sources.prepare", side_effect=disable_after_prepare):
            envelope = issue_mail(document, "envelope", django_capture_on_commit_callbacks, document_mail)
        delivery = envelope.deliveries.get(channel="email")
        expected_error = "transport_suppressed"
        logs = EmailLog.objects.filter(event="document_issued", source_id=str(envelope.pk),
            recipient_id=document.payment.member_id, source_metadata__delivery_id=delivery.pk)
        assert logs.count() == 1
        reason = "Email is disabled for this makerspace." if switch == "email" else "notification_source_disabled"
        assert (logs.get().status, logs.get().error, logs.get().attempts) == ("skipped", reason, 0)
    delivery.refresh_from_db()
    assert (delivery.state, delivery.last_error, delivery.attempt_count) == ("skipped", expected_error, 1)
    assert mailoutbox == [] and document_mail.rendered == []
    history = NotificationDelivery.objects.values().get(pk=delivery.pk)
    log_history = list(EmailLog.objects.filter(event="document_issued").values())
    set_switch(lane.space, switch, True)
    assert issue_mail(document, "envelope", django_capture_on_commit_callbacks, document_mail).pk == envelope.pk
    send(delivery.pk)
    deliver_envelope(envelope.pk)
    assert mailoutbox == [] and document_mail.rendered == []
    assert NotificationDelivery.objects.values().get(pk=delivery.pk) == history
    assert list(EmailLog.objects.filter(event="document_issued").values()) == log_history
    # A fresh target_key avoids uniq_envelope_delivery, proving the broader
    # uniq_envelope_channel constraint independently blocks a second attempt.
    with pytest.raises(IntegrityError, match="uniq_envelope_channel"):
        with transaction.atomic():
            NotificationDelivery.objects.create(makerspace=lane.space, envelope=envelope,
                channel="email", target_key="explicit-document-recovery:1", provider="builtin")
    assert envelope.deliveries.filter(channel="email").count() == 1
    assert document_ledger_snapshot(document) == original


@pytest.mark.parametrize("switch", ["email", "billing.documents"])
def test_0120_reserved_then_disabled_email_leg_stays_skipped_on_explicit_reemit(
        document, document_mail, lane, switch, django_capture_on_commit_callbacks, mailoutbox):
    """Decision 515: no replacement leg/log or send until next release's model change."""
    original = document_ledger_snapshot(document)

    def disable_after_prepare(log):
        assert prepare(log) is True
        set_switch(lane.space, switch, False)
        return True

    with patch("apps.integrations.delivery_sources.prepare", side_effect=disable_after_prepare):
        envelope = issue_mail(document, "envelope", django_capture_on_commit_callbacks, document_mail)
    delivery = envelope.deliveries.get(channel="email")
    assert (delivery.state, delivery.last_error, delivery.attempt_count) == ("skipped", "transport_suppressed", 1)
    logs = EmailLog.objects.filter(event="document_issued", source_id=envelope.pk,
        recipient_id=document.payment.member_id, source_metadata__delivery_id=delivery.pk)
    assert logs.count() == 1
    log = logs.get()
    reason = "Email is disabled for this makerspace." if switch == "email" else "notification_source_disabled"
    assert (log.status, log.error, log.attempts) == ("skipped", reason, 0)
    deliveries = list(envelope.deliveries.order_by("pk").values())
    history = list(EmailLog.objects.filter(event="document_issued").order_by("pk").values())
    assert len(deliveries) == 1 and len(history) == 1
    queued = lane.enqueued.count(envelope.pk)
    set_switch(lane.space, switch, True)
    for _ in range(2):
        assert issue_mail(document, "envelope", django_capture_on_commit_callbacks, document_mail).pk == envelope.pk
        send(delivery.pk)
        deliver_envelope(envelope.pk)
    assert lane.enqueued.count(envelope.pk) == queued
    assert mailoutbox == [] and document_mail.rendered == []
    assert NotificationEnvelope.objects.filter(dedup_key=envelope.dedup_key).count() == 1
    assert list(envelope.deliveries.order_by("pk").values()) == deliveries
    assert list(EmailLog.objects.filter(event="document_issued").order_by("pk").values()) == history
    assert document_ledger_snapshot(document) == original
