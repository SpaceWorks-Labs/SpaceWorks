"""R9: completed unresolved document passes cannot occupy every bounded sweep."""
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.db import connection
from django.utils import timezone

from apps.hardware_requests.models import HardwareRequest
from apps.integrations.document_email_state import initialize
from apps.integrations.mail_providers.delivery import send as smtp_send
from apps.integrations.models import DailyEmailCounter, EmailLog
from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from apps.integrations.models_document_email import DocumentEmailIntent
from apps.integrations.notification_tasks import deliver_envelope, sweep_notification_outbox
from apps.notifications.models_preferences import NotificationPreference
from apps.payments.documents import issue_bill
from apps.payments.models import Payment, PaymentDocument
from apps.payments.notifications_p2 import notify_document, notify_payment
from tests.billing_docs.test_email_recovery import set_switch
from tests.billing_docs.test_email_recovery_orderings import DISABLED, business_snapshot

pytestmark = pytest.mark.django_db(transaction=True)


def test_200_unresolved_documents_do_not_starve_201st_or_unrelated_ledger_envelope(
        document, document_mail, lane, settings, monkeypatch, mailoutbox,
        django_capture_on_commit_callbacks):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    fixture_envelope = document_mail.route("envelope")
    NotificationEnvelope.objects.filter(makerspace=fixture_envelope.makerspace).update(processed_at=timezone.now())
    # Acknowledge ambient receipt-fixture notices before building the measured queue.
    # Bulk fixtures keep setup cheap; initialization, emission, sweep and workers are real.
    loans = HardwareRequest.objects.bulk_create([HardwareRequest(makerspace=lane.space,
        requester=document.payment.member, requester_username=document.payment.member.username,
        status="accepted") for _ in range(200)])
    debts = Payment.objects.bulk_create([Payment(makerspace=lane.space, member=document.payment.member,
        subject_type="loan_deposit", subject_id=loan.pk, amount="25.00",
        currency="usd", provider="unclaimed", created_by=lane.manager) for loan in loans])
    documents = PaymentDocument.objects.bulk_create([PaymentDocument(makerspace=lane.space, payment=debt,
        sequence=1000 + index, number=f"SWEEP-BILL-{index}", kind="bill", issuer=document.issuer,
        payer_label=document.payer_label, payer_type="member", lines=document.lines,
        amount=debt.amount, currency=debt.currency, money_at=debt.created_at, issued_by=lane.manager)
        for index, debt in enumerate(debts)])
    for index, row in enumerate(documents):
        if index == 0:
            set_switch(lane.space, "email", False)
        initialize(row)
        with django_capture_on_commit_callbacks(execute=True):
            notify_document(row, initial=True)
        if index == 0:
            set_switch(lane.space, "email", True)
            row.makerspace.refresh_from_db()
            with django_capture_on_commit_callbacks(execute=True):
                notify_document(row)
    older = list(NotificationEnvelope.objects.filter(source_kind="payments.document",
        source_id__in=[str(row.pk) for row in documents]).order_by("pk"))
    older_ids = [row.pk for row in older]
    assert len(older_ids) == 200
    intents = DocumentEmailIntent.objects.filter(document__in=documents).order_by("pk")
    assert list(intents.values_list("state", "generation", "owner_kind", "owner_id")) == [
        ("recovery_approved", 1, "", None), *[("initial_pending", 0, "", None)] * 199]
    intent_history = list(intents.values())
    history = list(EmailLog.objects.filter(event="document_issued").order_by("pk").values())
    assert [(row["status"], row["error"], row["attempts"]) for row in history] == [("skipped", DISABLED, 0)]
    sibling = NotificationDelivery.objects.create(makerspace=lane.space, envelope=older[0], channel="telegram",
        target_key="prior-private-endpoint", provider="telegram", state="sent", attempt_count=1,
        provider_id="prior-accepted-document")
    sibling_history = NotificationDelivery.objects.values().get(pk=sibling.pk)
    revisions = {row.pk: row.revision for row in older}
    NotificationEnvelope.objects.filter(pk__in=older_ids).update(revision="ineligible-source-revision")

    healthy = lane.account("sweep-unrelated-payer")
    NotificationPreference.objects.filter(makerspace=lane.space, user=healthy, category="payments").update(channels=["email"])
    healthy_loan = HardwareRequest.objects.create(makerspace=lane.space, requester=healthy,
        requester_username=healthy.username, status="accepted")
    healthy_debt = Payment.objects.create(makerspace=lane.space, member=healthy, subject_type="loan_deposit",
        subject_id=healthy_loan.pk, amount="25.00", currency="usd", provider="unclaimed", created_by=lane.manager)
    # Simulate broker loss only: the durable intents are committed normally.
    with patch("apps.integrations.notification_outbox.enqueue") as lost, django_capture_on_commit_callbacks(execute=True):
        newer_document = issue_bill(healthy_debt, actor=lane.manager)
        notify_payment(healthy_debt, "charge_raised", requester_only=True)
    newer = NotificationEnvelope.objects.get(source_kind="payments.document", source_id=str(newer_document.pk))
    unrelated = NotificationEnvelope.objects.get(source_kind="payments.ledger", source_id=str(healthy_debt.pk), event="charge_raised")
    assert [call.args for call in lost.call_args_list] == [(newer.pk,), (unrelated.pk,)]
    assert max(older_ids) < newer.pk < unrelated.pk
    original, queued = business_snapshot(lane.space), list(lane.enqueued)
    counters = list(DailyEmailCounter.objects.filter(makerspace=lane.space).order_by("pk").values())
    smtp = Mock(wraps=smtp_send)
    monkeypatch.setattr("apps.integrations.mail_providers.delivery.send", smtp)
    now = timezone.now()

    def sweep(at, expected):
        with patch("apps.integrations.notification_tasks.timezone.now", return_value=at), patch(
                "apps.integrations.notification_tasks.deliver_envelope.delay") as enqueued:
            sweep_notification_outbox()
            selected = [call.args[0] for call in enqueued.call_args_list]
            assert selected == expected
            for pk in selected:
                deliver_envelope(pk)
        assert not connection.in_atomic_block
        assert business_snapshot(lane.space) == original
        assert list(lane.enqueued) == queued
        assert NotificationDelivery.objects.values().get(pk=sibling.pk) == sibling_history
        assert list(EmailLog.objects.filter(pk__in=[row["id"] for row in history]).order_by("pk").values()) == history

    def unresolved():
        assert list(intents.values()) == intent_history
        assert NotificationDelivery.objects.filter(envelope_id__in=older_ids, channel="email").count() == 0
        assert EmailLog.objects.filter(source_kind="notification.envelope", source_id__in=older_ids).count() == 0
        assert NotificationEnvelope.objects.filter(pk__in=older_ids, processed_at__isnull=True).count() == 200

    sweep(now, older_ids)
    unresolved()
    assert list(NotificationEnvelope.objects.filter(pk__in=older_ids).order_by("pk").values_list("available_at", flat=True)) == [now + timedelta(minutes=5)] * 200
    assert list(DailyEmailCounter.objects.filter(makerspace=lane.space).order_by("pk").values()) == counters
    assert smtp.call_count == 0 and document_mail.rendered == [] and mailoutbox == []
    # Even a late sweep (past the retry deadline) must prefer never-processed
    # newer work to the same 200 completed no-target passes.
    late = now + timedelta(minutes=6)
    sweep(late, [newer.pk, unrelated.pk, *older_ids[:198]])
    unresolved()
    assert smtp.call_count == 2 and document_mail.rendered == [newer_document.pk]
    assert [message.to for message in mailoutbox] == [[healthy.email], [healthy.email]]
    assert mailoutbox[0].attachments == [(f"{newer_document.number}.pdf", b"%PDF-1.7\nprivate-payer-document-1", "application/pdf")]
    assert mailoutbox[1].attachments == []
    assert list(NotificationDelivery.objects.filter(envelope__in=[newer, unrelated]).order_by("envelope_id").values_list(
        "channel", "state", "last_error", "attempt_count", "retryable")) == [("email", "sent", "", 1, False)] * 2
    counters_after_healthy = list(DailyEmailCounter.objects.filter(makerspace=lane.space).order_by("pk").values())
    sweep(late, older_ids[198:])
    unresolved()
    assert list(DailyEmailCounter.objects.filter(makerspace=lane.space).order_by("pk").values()) == counters_after_healthy
    sweep(late, [])

    # Existing generation-1 permission remains usable when just one source
    # returns. No new approval, erased history or live-eligibility bypass.
    NotificationEnvelope.objects.filter(pk=older[0].pk).update(revision=revisions[older[0].pk])
    sweep(now + timedelta(minutes=12), older_ids)
    recovered = DocumentEmailIntent.objects.get(document=documents[0])
    leg = older[0].deliveries.get(channel="email")
    assert (recovered.state, recovered.generation, recovered.owner_kind, recovered.owner_id) == ("sent", 1, "envelope", leg.pk)
    assert (leg.state, leg.last_error, leg.attempt_count, leg.retryable) == ("sent", "", 1, False)
    assert list(intents.exclude(pk=recovered.pk).values()) == intent_history[1:]
    assert smtp.call_count == 3 and document_mail.rendered == [newer_document.pk, documents[0].pk]
    assert [message.to for message in mailoutbox] == [[healthy.email], [healthy.email], [document.payment.member.email]]
    assert mailoutbox[2].attachments == [(f"{documents[0].number}.pdf", b"%PDF-1.7\nprivate-payer-document-2", "application/pdf")]
    assert list(EmailLog.objects.filter(status="sent").order_by("pk").values_list(
        "source_kind", "source_id", "recipient_id", "error", "attempts")) == [
        ("notification.envelope", newer.pk, healthy.pk, "", 1),
        ("notification.envelope", unrelated.pk, healthy.pk, "", 1),
        ("notification.envelope", older[0].pk, document.payment.member_id, "", 1)]
    saved = (list(NotificationEnvelope.objects.filter(pk__in=[newer.pk, unrelated.pk, older[0].pk]).order_by("pk").values()),
        list(EmailLog.objects.order_by("pk").values()), list(intents.values()))
    for pk in [newer.pk, unrelated.pk, older[0].pk] * 2:
        deliver_envelope(pk)
    sweep(now + timedelta(minutes=12), [])
    assert (list(NotificationEnvelope.objects.filter(pk__in=[newer.pk, unrelated.pk, older[0].pk]).order_by("pk").values()),
        list(EmailLog.objects.order_by("pk").values()), list(intents.values())) == saved
    assert smtp.call_count == 3 and len(mailoutbox) == 3
