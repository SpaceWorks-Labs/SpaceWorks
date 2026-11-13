"""F1 payment consumer: durable claims, local days and owner-only disclosure."""

from tests.payments.membership_rows import community_membership
from datetime import datetime, timedelta, timezone as utc
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.integrations import notify
from apps.integrations.models import EmailLog, NotificationPreference
from apps.operations.models_reminders import ReminderSchedule
from apps.operations.reminder_services import schedule_reminders
from apps.operations.reminder_sweeper import run_reminder_sweep as _run_reminder_sweep
from apps.integrations.models_contract import NotificationEnvelope
from apps.notifications.models_inbox import NotificationInboxRow
from tests.test_notification_families_f3 import capture_delivery
from apps.payments.models import MakerspaceBillingSettings
from apps.payments.reminders import _steps
from apps.payments.services_refunds_offline import amend_offline_refund, record_offline_refund
from tests.module_helpers import disable_module
from tests.payments.test_billing_due_p5 import new_charge
from tests.payments.test_offline_refunds import cash_deposit, payload
from tests.payments.account_helpers import make_payer
from tests.return_helpers import make_member, make_space

pytestmark = pytest.mark.django_db(transaction=True)


def run_reminder_sweep(*, now, **kwargs):
    # Delivery rechecks the live reminder clock as well as the scheduler clock.
    from unittest.mock import patch
    with patch("django.utils.timezone.now", return_value=now):
        return _run_reminder_sweep(now=now, **kwargs)


def reminder_space(slug):
    space = make_space(slug)
    space.enabled_modules = sorted(set(space.enabled_modules) | {"notifications", "email"})
    space.enabled_features = sorted(set(space.enabled_features) | {"billing.reminders"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    disable_module(space, "payments")
    payer = make_payer(f"{slug}-payer", space)
    payer.email_verified_at = timezone.now()
    payer.save(update_fields=["email_verified_at"])
    space.enabled_features = sorted(set(space.enabled_features) | {"notifications.member_inbox"})
    space.save(update_fields=["enabled_features"])
    from apps.notifications.models_preferences import NotificationPreference as PersonalPreference
    PersonalPreference.objects.create(makerspace=space, user=payer, category="payments", channels=["email", "in_app"])
    NotificationPreference.objects.create(makerspace=space, feature="payments", channel="email", enabled=True)
    return space, payer


@pytest.fixture
def deliveries(monkeypatch):
    return capture_delivery(monkeypatch)


def test_due_today_and_overdue_ladder_dispatch_once_only_to_owner(deliveries):
    space, payer = reminder_space("p6-once")
    MakerspaceBillingSettings.objects.create(makerspace=space, reminder_days_after=[3, 7], max_reminders=4)
    now = datetime(2026, 10, 10, 12, tzinfo=utc.utc)
    payment = new_charge(space, payer, due_at=now)
    # Creation is a separate edge; inspect only sweeper dispatches.
    emails, channels = deliveries
    emails.clear()
    assert run_reminder_sweep(now=now)["dispatched"] == 1
    assert run_reminder_sweep(now=now)["dispatched"] == 0
    assert [row["to_email"] for row in emails] == [payer.email]
    assert all(row["audience"] == "requester" for row in emails)
    assert channels == []
    emails.clear()
    assert run_reminder_sweep(now=now + timedelta(days=3))["dispatched"] == 1
    assert run_reminder_sweep(now=now + timedelta(days=3))["dispatched"] == 0
    assert "payment overdue" in emails[0]["text_body"]
    payment.refresh_from_db()
    assert payment.status == "pending"


def test_due_soon_then_today_are_distinct_idempotent_steps(deliveries):
    space, payer = reminder_space("p6-before")
    now = datetime(2026, 10, 10, 12, tzinfo=utc.utc)
    new_charge(space, payer, due_at=now + timedelta(days=3))
    emails, _ = deliveries
    emails.clear()
    assert run_reminder_sweep(now=now)["dispatched"] == 1
    assert "payment due soon" in emails[0]["text_body"]
    assert run_reminder_sweep(now=now + timedelta(days=3))["dispatched"] == 1
    assert "payment due today" in emails[-1]["text_body"]


def test_downtime_expires_due_today_and_sends_only_latest_overdue_step(deliveries):
    space, payer = reminder_space("p6-downtime")
    MakerspaceBillingSettings.objects.create(makerspace=space, reminder_days_after=[3, 7], max_reminders=4)
    due = datetime(2026, 10, 10, 12, tzinfo=utc.utc)
    new_charge(space, payer, due_at=due)
    emails, channels = deliveries
    emails.clear()
    assert run_reminder_sweep(now=due + timedelta(days=2))["dispatched"] == 0
    assert not emails
    assert run_reminder_sweep(now=due + timedelta(days=10))["dispatched"] == 1
    assert len(emails) == 1 and "payment overdue" in emails[0]["text_body"]
    assert "payment due today" not in emails[0]["text_body"]
    assert run_reminder_sweep(now=due + timedelta(days=10))["dispatched"] == 0
    assert not channels


@pytest.mark.parametrize("gate", ["notifications", "email", "feature", "matrix"])
def test_disabled_reminders_do_not_claim_or_send(gate, deliveries):
    space, payer = reminder_space(f"p6-gate-{gate}")
    now = timezone.now()
    new_charge(space, payer, due_at=now)
    emails, _ = deliveries
    emails.clear()
    if gate in {"notifications", "email"}:
        disable_module(space, gate)
    elif gate == "feature":
        space.enabled_features = [key for key in space.enabled_features if key != "billing.reminders"]
        space.save(update_fields=["enabled_features"])
    else:
        NotificationPreference.objects.filter(makerspace=space, feature="payments", channel="email").update(enabled=False)
    dispatched = run_reminder_sweep(now=now)["dispatched"]
    if gate in {"email", "matrix"}:
        # Mail being off cannot cancel the owner's in-app/chat reminder intent.
        assert dispatched == 1
        assert ReminderSchedule.objects.filter(makerspace=space).exists()
        assert NotificationEnvelope.objects.filter(makerspace=space, event="payment_due_today", recipient=payer).exists()
        assert NotificationInboxRow.objects.filter(makerspace=space, user=payer, event="payment_due_today").exists()
    else:
        assert dispatched == 0
        assert not ReminderSchedule.objects.filter(makerspace=space).exists()
    assert not emails


def test_default_off_and_maximum_zero_prevent_automatic_mail(deliveries):
    space = make_space("p6-default-off")
    payer = make_payer("p6-default-payer", space)
    now = timezone.now()
    new_charge(space, payer, due_at=now)
    assert run_reminder_sweep(now=now)["dispatched"] == 0
    space, payer = reminder_space("p6-zero")
    MakerspaceBillingSettings.objects.create(makerspace=space, max_reminders=0)
    new_charge(space, payer, due_at=now)
    assert run_reminder_sweep(now=now)["dispatched"] == 0


def test_settlement_and_foreign_subject_are_revalidated_before_dispatch(deliveries):
    space, payer = reminder_space("p6-scope-own")
    other, other_payer = reminder_space("p6-scope-other")
    now = timezone.now()
    payment = new_charge(other, other_payer, due_at=now)
    due, _ = _steps(other, payment)
    schedule_reminders(makerspace=space, source="payments.due", subject=str(payment.pk), kind="day:0", due_at=due)
    # Settle between schedule creation and dispatch; neither tenant may mail the row.
    from apps.payments.reconciliation import mark_offline
    from tests.return_helpers import settlement_details
    mark_offline(payment, make_member("p6-scope-other-manager", other), settlement_details())
    emails, _ = deliveries
    emails.clear()
    assert run_reminder_sweep(now=now)["dispatched"] == 0
    assert not emails
    assert ReminderSchedule.objects.get(makerspace=space).state == "completed"


@pytest.mark.parametrize("status,opted_out", [("revoked", False), ("active", True)])
def test_reminders_respect_member_revocation_and_opt_out(status, opted_out, deliveries):
    from apps.makerspaces.models import MakerspaceMembership
    space, payer = reminder_space("p6-member-preference")
    now = timezone.now()
    new_charge(space, payer, due_at=now)
    MakerspaceMembership.objects.filter(makerspace=space, user=payer).update(
        status=status, receives_notifications=not opted_out,
    )
    emails, channels = deliveries
    emails.clear()
    run_reminder_sweep(now=now)
    assert not emails and not channels


def test_small_discovery_batches_advance_beyond_scheduled_ladders(deliveries):
    space, payer = reminder_space("p6-batches")
    now = timezone.now()
    new_charge(space, payer, due_at=now)
    second = make_payer("p6-batch-second", space)
    second.email_verified_at = timezone.now()
    second.save(update_fields=["email_verified_at"])
    new_charge(space, second, due_at=now)
    for _ in range(10):
        run_reminder_sweep(now=now, limit=1)
    emails, _ = deliveries
    reminders = [row for row in emails if "payment due today" in row["text_body"]]
    assert len(reminders) == 2


def test_dst_steps_follow_local_calendar_days():
    space, payer = reminder_space("p6-dst")
    space.timezone = "America/New_York"
    space.save(update_fields=["timezone"])
    MakerspaceBillingSettings.objects.create(makerspace=space, reminder_days_before=[], reminder_days_after=[1])
    payment = new_charge(space, payer, due_at=datetime(2026, 3, 8, 15, tzinfo=utc.utc))
    _, offsets = _steps(space, payment)
    assert offsets == (0, 23 * 3600)


def test_payer_receipt_defaults_on_but_explicit_matrix_off_wins(deliveries):
    space = make_space("p6-receipt-default")
    payer = make_payer("p6-receipt-payer", space)
    payer.email_verified_at = timezone.now()
    payer.save(update_fields=["email_verified_at"])
    from apps.payments.models import Payment
    from apps.makerspaces.models import MakerspaceMembership
    payment = Payment.objects.create(makerspace=space, member=payer, created_by=payer,
        subject_type="makerspace_membership",
        subject_id=community_membership(space, payer).pk,
        amount="10.00", currency="usd", status="paid_online")
    from apps.payments.notifications import notify_payment
    emails, channels = deliveries
    notify_payment(payment, "payment_received")
    assert [row["to_email"] for row in emails] == [payer.email]
    assert emails[0]["audience"] == "requester" and not channels
    emails.clear()
    NotificationPreference.objects.create(makerspace=space, feature="payments", channel="email", enabled=False)
    notify_payment(payment, "payment_received")
    assert not emails
    from apps.integrations.notification_resolution import resolve
    envelope = NotificationEnvelope.objects.get(makerspace=space, event="payment_received", recipient=payer)
    assert not any(target.channel == "email" for target in resolve(envelope))


def test_receipt_correction_does_not_emit_second_refund_event(monkeypatch):
    _, staff, payment = cash_deposit("p6-refund-event")
    events = []
    monkeypatch.setattr("apps.payments.notifications.notify_payment", lambda payment, event, **kwargs: events.append(event))
    refund = record_offline_refund(payment, actor=staff, **payload("3.00"))
    amend_offline_refund(payment, actor=staff, refund_id=refund.pk, receipt=payload(reference="fixed")["receipt"])
    assert events == ["refund_issued"]
