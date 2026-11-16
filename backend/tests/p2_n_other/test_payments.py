from datetime import timedelta

import pytest
from django.db import transaction
from django.utils import timezone

from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_sources import source_eligible
from apps.integrations.notification_resolution import resolve
from apps.payments.notifications import notify_payment
from apps.payments.reconciliation import mark_offline
from tests.module_helpers import disable_module
from tests.return_helpers import settlement_details

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("event", ["charge_raised", "payment_due_soon", "payment_due_today", "payment_overdue", "payment_failed"])
def test_pending_payment_rows_reach_account_only_owner_without_email_or_rail(lane, payment, event):
    disable_module(lane.space, "membership")
    disable_module(lane.space, "payments")
    disable_module(lane.space, "email")
    payment.makerspace.refresh_from_db()
    notify_payment(payment, event)
    envelope = lane.deliver(event, payment.member)
    assert source_eligible(envelope)
    assert envelope.deliveries.get(channel="telegram").state == "accepted"
    assert "25.00" in lane.fake.calls[-1][1]["text"]
    assert not payment.member.makerspace_memberships.exists()
    if event != "charge_raised":
        assert not NotificationEnvelope.objects.filter(event=event, audience="staff").exists()


def test_settlement_receipt_document_and_refund_rows_use_ledger(lane, payment):
    from apps.payments.services_refunds_offline import record_offline_refund
    mark_offline(payment, lane.manager, settlement=settlement_details())
    payment.refresh_from_db()
    receipt = lane.deliver("payment_received", payment.member)
    assert source_eligible(receipt)
    document = lane.deliver("document_issued", payment.member)
    assert source_eligible(document)
    assert "25.00" in lane.fake.calls[-1][1]["text"]
    assert "token=" not in lane.fake.calls[-1][1]["text"]
    refund = record_offline_refund(payment, amount="5.00", reason="Partial return", actor=lane.manager,
        receipt={"method": "cash", "reference": "desk", "refunded_at": timezone.now()})
    notice = lane.deliver("refund_issued", payment.member)
    assert source_eligible(notice)
    assert "5.00" in lane.fake.calls[-1][1]["text"]
    staff = NotificationEnvelope.objects.get(event="refund_issued", audience="staff")
    from apps.integrations.notification_sources import render
    assert "5.00" not in render(staff)["text"]
    assert str(refund.pk) == str(notice.context["refund_id"])


def test_charge_dedup_survives_checkout_metadata_changes(lane, payment):
    notify_payment(payment, "charge_raised")
    payment.subject_label = "Updated label"
    payment.save(update_fields=["subject_label", "updated_at"])
    notify_payment(payment, "charge_raised")
    assert NotificationEnvelope.objects.filter(recipient=payment.member, event="charge_raised").count() == 1


def test_settled_debt_and_revoked_owner_stop_queued_payment_notices(lane, payment):
    notify_payment(payment, "payment_overdue")
    envelope = NotificationEnvelope.objects.get(event="payment_overdue")
    mark_offline(payment, lane.manager, settlement=settlement_details())
    assert resolve(envelope) == []


def test_payment_transaction_rollback_removes_envelope(lane, payment):
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            notify_payment(payment, "charge_raised")
            raise RuntimeError("rollback")
    assert not NotificationEnvelope.objects.exists()


def test_dunning_discovery_does_not_depend_on_email_module(lane, payment):
    from apps.payments.reminders import discover_payments
    disable_module(lane.space, "email")
    # Discovery yields the due-day step even while only chat can deliver it.
    assert list(discover_payments(lane.space, timezone.now(), 20, None))


def test_distinct_reminder_steps_are_not_collapsed(lane, payment):
    from apps.operations.models_reminders import ReminderSchedule
    now = timezone.now()
    notices = []
    for day in (0, 1):
        reminder = ReminderSchedule.objects.create(makerspace=lane.space, source="payments.due",
            subject=str(payment.pk), kind=f"day:{day}", offset_seconds=day*86400,
            due_at=now, remind_at=now+timedelta(days=day))
        notify_payment(payment, "payment_overdue", reminder=reminder)
        notices.append(reminder.pk)
    assert set(NotificationEnvelope.objects.filter(recipient=payment.member).values_list(
        "context__reminder_id", flat=True)) == set(notices)


def test_multiple_selected_media_receive_one_owner_intent_each(lane, payment, monkeypatch):
    from apps.integrations.models_endpoints import ChannelConfiguration, NotificationEndpoint
    from apps.integrations.notification_fake import FakeProvider
    from apps.integrations.notification_providers import PROVIDERS
    from apps.integrations.models import NotificationPreference as Matrix
    from apps.notifications.models_preferences import NotificationPreference
    config = ChannelConfiguration.objects.create(makerspace=lane.space, channel="slack", provider="slack",
        enabled=True, personal_enabled=True, integration_identity="workspace-123")
    fake = FakeProvider(config)
    monkeypatch.setitem(PROVIDERS, ("slack", "slack"), lambda _: fake)
    NotificationEndpoint.objects.create(makerspace=lane.space, user=payment.member, configuration=config,
        channel="slack", provider="slack", destination="private-slack-id", provider_subject="slack-user",
        identity_digest="d"*64, integration_identity=config.integration_identity, integration_generation=config.generation,
        verified_at=timezone.now(), consented_at=timezone.now(), consent_version="v1")
    Matrix.objects.create(makerspace=lane.space, feature="payments", channel="slack", enabled=True)
    NotificationPreference.objects.filter(makerspace=lane.space, user=payment.member, category="payments").update(
        channels=["telegram", "slack"])
    notify_payment(payment, "charge_raised")
    envelope = lane.deliver("charge_raised", payment.member)
    assert set(envelope.deliveries.values_list("channel", flat=True)) == {"telegram", "slack"}
    assert len(lane.fake.calls) == len(fake.calls) == 1


def test_foreign_source_reference_is_refused_even_for_a_live_account(lane, payment):
    from tests.return_helpers import make_space
    notify_payment(payment, "charge_raised")
    envelope = NotificationEnvelope.objects.get(recipient=payment.member)
    other = make_space("p2-foreign-source")
    # Simulate a corrupted caller binding: source lookup must remain tenant-scoped.
    envelope.makerspace = other
    assert not source_eligible(envelope)


def test_payment_document_keeps_direct_payer_mail(lane, payment, django_capture_on_commit_callbacks, monkeypatch):
    from apps.integrations.models import EmailLog
    monkeypatch.setattr("apps.integrations.dispatch._deliver", lambda log, *a, **k: log, raising=False)
    with django_capture_on_commit_callbacks(execute=True):
        mark_offline(payment, lane.manager, settlement=settlement_details())
    mail = EmailLog.objects.filter(event="document_issued", source_metadata__has_key="p2_direct")
    assert mail.count() == 1 and mail.get().to_email == payment.member.email
    assert mail.get().text_body == ""  # persist_body=False, exactly as before
