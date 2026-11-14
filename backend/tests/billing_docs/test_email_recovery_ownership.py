"""Changing the tenant matrix cannot give a document email a second owner."""
from threading import Lock
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from apps.integrations.mail_providers.delivery import send as smtp_send
from apps.integrations.models import DailyEmailCounter, EmailLog, NotificationPreference as Matrix
from apps.integrations.models_contract import NotificationDelivery
from apps.integrations.notification_delivery import ensure_deliveries, send
from apps.integrations.notification_tasks import deliver_envelope
from apps.notifications.models_preferences import NotificationPreference
from apps.notifications.models import MemberNotificationPreference
from apps.payments.notifications_p2 import notify_document
from tests.billing_docs.test_email_recovery import set_switch
from tests.billing_docs.test_email_recovery_concurrency import contend_at_envelope_lock
from tests.billing_docs.test_email_recovery_quota import reserve
from tests.billing_docs.test_r2_email import assert_mail_owner, document_ledger_snapshot, issue_mail

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("owner_state", ["sent", "retrying", "reserved", "refused", "disabled"])
def test_matrix_change_cannot_replace_existing_envelope_email_owner(
        document, document_mail, lane, settings, monkeypatch, owner_state,
        django_capture_on_commit_callbacks, mailoutbox):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    lane.space.email_provider = "resend"
    lane.space.resource_limit_overrides = {**lane.space.resource_limit_overrides, "email": 1}
    lane.space.save(update_fields=["email_provider", "resource_limit_overrides"])
    smtp = Mock(wraps=smtp_send)
    monkeypatch.setattr("apps.integrations.mail_providers.delivery.send", smtp)
    original = document_ledger_snapshot(document)
    set_switch(lane.space, "email", False)
    envelope = issue_mail(document, "envelope", django_capture_on_commit_callbacks, document_mail)
    history = EmailLog.objects.values().get(event="document_issued")
    assert (history["status"], history["error"], history["attempts"]) == (
        "skipped", "Email is disabled for this makerspace.", 0)
    assert (history["source_kind"], history["source_id"], history["recipient_id"]) == (
        "notification.direct", envelope.pk, document.payment.member_id)
    assert history["source_metadata"]["p2_direct"] == envelope.dedup_key
    assert envelope.deliveries.count() == 0
    assert DailyEmailCounter.objects.filter(makerspace=lane.space).count() == 0
    smtp.assert_not_called()
    set_switch(lane.space, "email", True)
    document.makerspace.refresh_from_db()
    queued = lane.enqueued.count(envelope.pk)
    with django_capture_on_commit_callbacks(execute=True):
        notify_document(document)
    assert lane.enqueued.count(envelope.pk) == queued + 1
    if owner_state == "reserved":
        ensure_deliveries(envelope)
    elif owner_state == "refused":
        ensure_deliveries(envelope)
        consent = MemberNotificationPreference.objects.create(makerspace=lane.space,
            user=document.payment.member, feature="payments", channel="email", enabled=False)
        send(envelope.deliveries.get(channel="email").pk)
        consent.enabled = True
        consent.save(update_fields=["enabled"])
    elif owner_state == "disabled":
        from apps.integrations.delivery_sources import prepare

        def disable_after_prepare(log):
            assert prepare(log) is True
            set_switch(lane.space, "email", False)
            return True

        with patch("apps.integrations.delivery_sources.prepare", side_effect=disable_after_prepare):
            deliver_envelope(envelope.pk)
        set_switch(lane.space, "email", True)
    elif owner_state == "retrying":
        with patch("apps.integrations.dispatch_delivery.EmailMultiAlternatives.send", side_effect=OSError("SMTP down")):
            deliver_envelope(envelope.pk)
    else:
        deliver_envelope(envelope.pk)
    delivery = envelope.deliveries.get(channel="email")
    expected = {"sent": ("sent", "", 1, False), "retrying": ("retrying", "provider_error", 1, True),
                "reserved": ("retrying", "", 0, False),
                "refused": ("skipped", "live_eligibility_changed", 1, False),
                "disabled": ("skipped", "transport_suppressed", 1, False)}[owner_state]
    assert (delivery.state, delivery.last_error, delivery.attempt_count, delivery.retryable) == expected
    assert envelope.deliveries.count() == 1
    if owner_state in {"reserved", "refused"}:
        assert EmailLog.objects.filter(event="document_issued").count() == 1
        assert DailyEmailCounter.objects.filter(makerspace=lane.space).count() == 0
        assert document_mail.rendered == [] and mailoutbox == []
        smtp.assert_not_called()
    elif owner_state == "disabled":
        attempt = EmailLog.objects.get(source_kind="notification.envelope", source_id=envelope.pk)
        assert EmailLog.objects.filter(event="document_issued").count() == 2
        assert (attempt.status, attempt.error, attempt.attempts) == (
            "skipped", "Email is disabled for this makerspace.", 0)
        assert attempt.source_metadata["delivery_id"] == delivery.pk
        assert DailyEmailCounter.objects.get(makerspace=lane.space, day=timezone.now().date()).count == 1
        assert document_mail.rendered == [] and mailoutbox == []
        smtp.assert_not_called()
    else:
        attempt = EmailLog.objects.get(source_kind="notification.envelope", source_id=envelope.pk)
        assert EmailLog.objects.filter(event="document_issued").count() == 2
        assert (attempt.status, attempt.error, attempt.attempts) == (
            ("sent", "", 1) if owner_state == "sent" else ("failed", "email_delivery_failed:OSError", 1))
        assert attempt.source_metadata["delivery_id"] == delivery.pk
        assert attempt.recipient_id == document.payment.member_id
        assert smtp.call_count == 1 and document_mail.rendered == [document.pk]
        assert DailyEmailCounter.objects.get(makerspace=lane.space, day=timezone.now().date()).count == 1
        assert len(mailoutbox) == (1 if owner_state == "sent" else 0)
        if owner_state == "sent":
            assert_mail_owner(document, "envelope", envelope, skipped_direct=1)
            assert mailoutbox[0].to == [document.payment.member.email]
            assert mailoutbox[0].attachments == [
                (f"{document.number}.pdf", b"%PDF-1.7\nprivate-payer-document-1", "application/pdf")]
    logs = list(EmailLog.objects.filter(makerspace=lane.space).order_by("pk").values())
    legs = list(NotificationDelivery.objects.filter(makerspace=lane.space).order_by("pk").values())
    counters = list(DailyEmailCounter.objects.filter(makerspace=lane.space).order_by("pk").values())
    assert document_ledger_snapshot(document) == original
    enqueued = list(lane.enqueued)
    smtp_count = smtp.call_count
    pdfs = list(document_mail.rendered)
    # Change ONLY the tenant matrix; the payer's explicit email consent stays on.
    Matrix.objects.filter(makerspace=lane.space, feature="payments", channel="email").update(enabled=False)
    assert NotificationPreference.objects.get(makerspace=lane.space, user=document.payment.member,
        category="payments").channels == ["email"]
    with patch("apps.integrations.dispatch_outbox._enqueue") as enqueue:
        for _ in range(2):
            with django_capture_on_commit_callbacks(execute=True):
                notify_document(document)
            # Exercise the reservation itself too: no outer producer check is sufficient.
            with django_capture_on_commit_callbacks(execute=True):
                assert reserve(document.pk, envelope) is None
        enqueue.assert_not_called()
    assert lane.enqueued == enqueued
    assert smtp.call_count == smtp_count
    assert document_mail.rendered == pdfs
    assert len(mailoutbox) == (1 if owner_state == "sent" else 0)
    assert list(EmailLog.objects.filter(makerspace=lane.space).order_by("pk").values()) == logs
    assert list(NotificationDelivery.objects.filter(makerspace=lane.space).order_by("pk").values()) == legs
    assert list(DailyEmailCounter.objects.filter(makerspace=lane.space).order_by("pk").values()) == counters
    assert EmailLog.objects.values().get(pk=history["id"]) == history
    assert document_ledger_snapshot(document) == original


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("first_owner", ["direct", "envelope"])
def test_overlapping_document_owners_share_the_envelope_reservation_lock(
        document, document_mail, lane, settings, first_owner,
        django_capture_on_commit_callbacks, mailoutbox):
    from apps.integrations.dispatch_delivery import _deliver
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    lane.space.email_provider = "resend"
    lane.space.resource_limit_overrides = {**lane.space.resource_limit_overrides, "email": 1}
    lane.space.save(update_fields=["email_provider", "resource_limit_overrides"])
    set_switch(lane.space, "email", False)
    envelope = issue_mail(document, "envelope", django_capture_on_commit_callbacks, document_mail)
    history = EmailLog.objects.values().get(event="document_issued")
    assert (history["status"], history["error"]) == ("skipped", "Email is disabled for this makerspace.")
    set_switch(lane.space, "email", True)
    document.makerspace.refresh_from_db()
    with django_capture_on_commit_callbacks(execute=True):
        notify_document(document)
    original = document_ledger_snapshot(document)
    queued = list(lane.enqueued)
    entrants, attempts = [], []
    order_lock = Lock()

    def produce():
        with order_lock:
            owner = first_owner if not entrants else "envelope" if first_owner == "direct" else "direct"
            entrants.append(owner)
        if owner == "envelope":
            ensure_deliveries(envelope)
        else:
            attempts.append(reserve(document.pk, envelope))

    with patch("apps.integrations.dispatch_outbox._enqueue") as enqueue:
        contend_at_envelope_lock(produce)
    assert entrants == (["direct", "envelope"] if first_owner == "direct" else ["envelope", "direct"])
    assert len(attempts) == 1
    if first_owner == "direct":
        pending = EmailLog.objects.get(event="document_issued", status="pending")
        assert attempts[0].pk == pending.pk
        assert (pending.error, pending.attempts) == ("", 0)
        assert envelope.deliveries.filter(channel="email").count() == 0
        enqueue.assert_called_once_with(pending.pk)
        _deliver(pending)
    else:
        assert attempts == [None]
        enqueue.assert_not_called()
        assert EmailLog.objects.filter(event="document_issued").count() == 1
        leg = envelope.deliveries.get(channel="email")
        assert (leg.state, leg.last_error, leg.attempt_count) == ("retrying", "", 0)
        assert DailyEmailCounter.objects.filter(makerspace=lane.space).count() == 0
    deliver_envelope(envelope.pk)
    deliver_envelope(envelope.pk)
    assert_mail_owner(document, first_owner, envelope, skipped_direct=1)
    assert DailyEmailCounter.objects.get(makerspace=lane.space, day=timezone.now().date()).count == 1
    assert lane.enqueued == queued
    assert len(mailoutbox) == 1 and mailoutbox[0].to == [document.payment.member.email]
    assert mailoutbox[0].attachments == [
        (f"{document.number}.pdf", b"%PDF-1.7\nprivate-payer-document-1", "application/pdf")]
    assert document_mail.rendered == [document.pk]
    assert EmailLog.objects.values().get(pk=history["id"]) == history
    assert document_ledger_snapshot(document) == original
