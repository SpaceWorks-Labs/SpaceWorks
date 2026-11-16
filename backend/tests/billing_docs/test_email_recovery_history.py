"""Historical document skips require positive evidence and current authority."""
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.integrations.email_preferences import address_hash
from apps.integrations.models import EmailLog
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.models_suppression import EmailSuppression
from apps.integrations.notification_tasks import deliver_envelope
from tests.billing_docs.test_email_recovery import set_switch
from tests.billing_docs.test_r2_email import assert_mail_owner, document_ledger_snapshot, issue_mail, retry_mail

pytestmark = pytest.mark.django_db


def remove_marker(envelope):
    # Simulate a pre-530 intent: retained history exists, but no persisted state yet.
    from apps.integrations.models_document_email import DocumentEmailIntent
    DocumentEmailIntent.objects.filter(document_id=envelope.source_id).delete()
    envelope.refresh_from_db()
    envelope.routing_snapshot = {key: value for key, value in envelope.routing_snapshot.items()
                                 if not key.startswith("_disabled_dispatch")}
    envelope.save(update_fields=["routing_snapshot"])


def test_pre_marker_document_disabled_log_recovers_through_envelope_once(
        document, document_mail, lane, django_capture_on_commit_callbacks, mailoutbox):
    original = document_ledger_snapshot(document)
    set_switch(lane.space, "email", False)
    envelope = issue_mail(document, "envelope", django_capture_on_commit_callbacks, document_mail)
    deliver_envelope(envelope.pk)
    remove_marker(envelope)
    assert envelope.processed_at is not None and envelope.deliveries.count() == 0
    history = list(EmailLog.objects.filter(event="document_issued").values())
    assert len(history) == 1
    assert (history[0]["status"], history[0]["error"]) == (
        "skipped", "Email is disabled for this makerspace.")
    queued = lane.enqueued.count(envelope.pk)
    set_switch(lane.space, "email", True)
    # A worker cannot infer recovery from the retained log.
    deliver_envelope(envelope.pk)
    assert mailoutbox == [] and document_mail.rendered == []
    for _ in range(2):
        assert issue_mail(document, "envelope", django_capture_on_commit_callbacks, document_mail).pk == envelope.pk
        deliver_envelope(envelope.pk)
    assert lane.enqueued.count(envelope.pk) == queued + 1
    assert len(mailoutbox) == 1 and mailoutbox[0].to == [document.payment.member.email]
    assert mailoutbox[0].attachments == [
        (f"{document.number}.pdf", b"%PDF-1.7\nprivate-payer-document-1", "application/pdf")]
    assert document_mail.rendered == [document.pk]
    assert_mail_owner(document, "envelope", envelope, skipped_direct=1)
    assert list(EmailLog.objects.filter(pk=history[0]["id"]).values()) == history
    assert document_ledger_snapshot(document) == original


@pytest.mark.parametrize("refusal", ["email_member_opted_out", "email_address_suppressed"])
def test_pre_marker_disabled_history_cannot_override_retained_permanent_refusal(
        document, document_mail, lane, refusal, django_capture_on_commit_callbacks, mailoutbox):
    set_switch(lane.space, "email", False)
    envelope = issue_mail(document, "envelope", django_capture_on_commit_callbacks, document_mail)
    deliver_envelope(envelope.pk)
    remove_marker(envelope)
    skipped = EmailLog.objects.get(event="document_issued")
    EmailLog.objects.create(makerspace=lane.space, recipient=document.payment.member,
        source_kind=skipped.source_kind, source_id=skipped.source_id, source_metadata=skipped.source_metadata,
        event="document_issued", stream="payments", status="skipped", error=refusal)
    history = list(EmailLog.objects.filter(event="document_issued").order_by("pk").values())
    set_switch(lane.space, "email", True)
    issue_mail(document, "envelope", django_capture_on_commit_callbacks, document_mail)
    assert envelope.deliveries.count() == 0
    assert mailoutbox == [] and document_mail.rendered == []
    assert list(EmailLog.objects.filter(event="document_issued").order_by("pk").values()) == history


def test_pre_marker_reasonless_empty_document_envelope_is_not_guessed(
        document, document_mail, lane, django_capture_on_commit_callbacks, mailoutbox):
    set_switch(lane.space, "billing.documents", False)
    envelope = issue_mail(document, "envelope", django_capture_on_commit_callbacks, document_mail)
    remove_marker(envelope)
    assert envelope.processed_at is not None and envelope.deliveries.count() == 0
    assert EmailLog.objects.filter(event="document_issued").count() == 0
    history = NotificationEnvelope.objects.values().get(pk=envelope.pk)
    queued = lane.enqueued.count(envelope.pk)
    set_switch(lane.space, "billing.documents", True)
    issue_mail(document, "envelope", django_capture_on_commit_callbacks, document_mail)
    deliver_envelope(envelope.pk)
    assert NotificationEnvelope.objects.values().get(pk=envelope.pk) == history
    assert lane.enqueued.count(envelope.pk) == queued
    assert mailoutbox == [] and document_mail.rendered == []


@pytest.mark.parametrize("pre_marker", [False, True])
@pytest.mark.parametrize("authority", ["restricted", "inactive", "stale_source"])
def test_pre_marker_disabled_history_rechecks_current_source_and_recipient_authority(
        document, document_mail, lane, authority, pre_marker, django_capture_on_commit_callbacks, mailoutbox):
    from apps.integrations.notification_resolution import resolve
    original = document_ledger_snapshot(document)
    set_switch(lane.space, "email", False)
    envelope = issue_mail(document, "envelope", django_capture_on_commit_callbacks, document_mail)
    deliver_envelope(envelope.pk)
    if pre_marker:
        remove_marker(envelope)
    history = list(EmailLog.objects.filter(event="document_issued").values())
    assert len(history) == 1
    assert (history[0]["status"], history[0]["error"], history[0]["attempts"]) == (
        "skipped", "Email is disabled for this makerspace.", 0)
    assert (history[0]["source_kind"], history[0]["source_id"], history[0]["recipient_id"]) == (
        "notification.direct", envelope.pk, document.payment.member_id)
    assert history[0]["source_metadata"]["p2_direct"] == envelope.dedup_key
    set_switch(lane.space, "email", True)
    owner = document.payment.member
    revision = envelope.revision
    if authority == "stale_source":
        envelope.revision = "stale-document-source"
        envelope.save(update_fields=["revision"])
    elif authority == "inactive":
        owner.is_active = False
        owner.save(update_fields=["is_active"])
    else:
        owner.access_status = "restricted"
        owner.save(update_fields=["access_status"])
    assert resolve(envelope) == []
    refused = NotificationEnvelope.objects.values().get(pk=envelope.pk)
    queued = lane.enqueued.count(envelope.pk)
    issue_mail(document, "envelope", django_capture_on_commit_callbacks, document_mail)
    deliver_envelope(envelope.pk)
    assert mailoutbox == [] and document_mail.rendered == []
    assert envelope.deliveries.count() == 0
    assert list(EmailLog.objects.filter(event="document_issued").values()) == history
    assert NotificationEnvelope.objects.values().get(pk=envelope.pk) == refused
    assert lane.enqueued.count(envelope.pk) == queued
    assert not refused["routing_snapshot"].get("_disabled_dispatch_reemitted", False)
    assert document_ledger_snapshot(document) == original

    if authority == "stale_source":
        envelope.revision = revision
        envelope.save(update_fields=["revision"])
    elif authority == "inactive":
        owner.is_active = True
        owner.save(update_fields=["is_active"])
    else:
        owner.access_status = "active"
        owner.save(update_fields=["access_status"])
    assert [target.channel for target in resolve(envelope)] == ["email"]
    # Restoring standing alone still grants no automatic recovery.
    deliver_envelope(envelope.pk)
    assert mailoutbox == [] and document_mail.rendered == []
    assert lane.enqueued.count(envelope.pk) == queued
    for _ in range(2):
        assert issue_mail(document, "envelope", django_capture_on_commit_callbacks, document_mail).pk == envelope.pk
        deliver_envelope(envelope.pk)
    assert lane.enqueued.count(envelope.pk) == queued + 1
    assert envelope.deliveries.count() == 1
    assert len(mailoutbox) == 1 and mailoutbox[0].to == [owner.email]
    assert mailoutbox[0].attachments == [
        (f"{document.number}.pdf", b"%PDF-1.7\nprivate-payer-document-1", "application/pdf")]
    assert document_mail.rendered == [document.pk]
    assert_mail_owner(document, "envelope", envelope, skipped_direct=1)
    assert list(EmailLog.objects.filter(pk=history[0]["id"]).values()) == history
    assert document_ledger_snapshot(document) == original


@pytest.mark.parametrize("path", ["direct", "envelope"])
@pytest.mark.parametrize("suppress_current", [False, True])
def test_retry_checks_suppression_against_current_verified_payer_mailbox(
        document, document_mail, path, suppress_current, django_capture_on_commit_callbacks, mailoutbox):
    with patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("SMTP unavailable")):
        envelope = issue_mail(document, path, django_capture_on_commit_callbacks, document_mail)
    history = EmailLog.objects.values().get(event="document_issued", source_id=str(envelope.pk),
                                            recipient_id=document.payment.member_id)
    assert (history["status"], history["error"]) == ("failed", "email_delivery_failed:OSError")
    owner = document.payment.member
    old_address = owner.email
    EmailSuppression.objects.create(makerspace=document.makerspace,
        address_hash=address_hash(document.makerspace_id, old_address), reason="bounce")
    owner.email = "current-verified-payer@example.test"
    owner.save(update_fields=["email"])
    owner.email_verified_at = timezone.now()
    owner.save(update_fields=["email_verified_at"])
    if suppress_current:
        EmailSuppression.objects.create(makerspace=document.makerspace,
            address_hash=address_hash(document.makerspace_id, owner.email), reason="complaint")
    retry_mail(path, envelope)
    logs = EmailLog.objects.filter(event="document_issued", source_id=str(envelope.pk), recipient_id=owner.pk)
    if suppress_current:
        assert mailoutbox == [] and document_mail.rendered == [document.pk]
        assert logs.count() == 1
        if path == "direct":
            assert (logs.get().status, logs.get().error) == ("skipped", "email_address_suppressed")
        else:
            delivery = envelope.deliveries.get(channel="email")
            assert (delivery.state, delivery.last_error) == ("skipped", "live_eligibility_changed")
            assert logs.get().source_metadata["delivery_id"] == delivery.pk
            assert logs.values().get() == history
    else:
        assert document_mail.rendered == [document.pk, document.pk]
        assert len(mailoutbox) == 1 and mailoutbox[0].to == [owner.email]
        sent = logs.get(status="sent")
        assert (sent.error, sent.recipient_id) == ("", owner.pk)
        assert mailoutbox[0].attachments[0].content.endswith(b"-2")
    assert all(old_address not in message.to for message in mailoutbox)
