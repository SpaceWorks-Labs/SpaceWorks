"""Exact cancellation compensation, exercised through the real locked workflows."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

import pytest
from django.db import close_old_connections
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events import services
from apps.events.models import EventRegistration, EventTicketType
from apps.events.services_registration_tools import restore_registration
from apps.makerspaces.member_activity_service import _event_registrations
from apps.operations.cancellation_restore import RestoreRefused
from apps.payments.models import Payment
from tests.events.collab_helpers import client_for, make_staff
from tests.events.ticketing_helpers import account, event_space, open_event

pytestmark = pytest.mark.django_db


def setup_restore(*, approval=False, capacity=0):
    space = event_space("lane-b-restore")
    staff = make_staff(space)
    event = open_event(space, capacity=capacity, registration_requires_approval=approval)
    owner = account("lane-b-owner")
    registration = services.register(event, member=owner, actor=staff, staff_registration=True)
    return space, staff, event, owner, registration


def cancel(row, staff):
    return services.cancel_registration(row, actor=staff)


def assert_refusal(row, staff, reason):
    before = EventRegistration.objects.get(pk=row.pk)
    with pytest.raises(RestoreRefused) as failure:
        restore_registration(row, actor=staff)
    assert str(failure.value.detail["code"]) == reason
    row.refresh_from_db()
    assert (row.status, row.cancelled_at, row.calendar_sequence) == (
        before.status, before.cancelled_at, before.calendar_sequence,
    )
    assert not AuditLog.objects.filter(action="event.registration_restored").exists()


@pytest.mark.parametrize("approval,expected", [(False, "registered"), (True, "pending_approval")])
def test_restore_preserves_identity_exact_state_and_emits_lifecycle(approval, expected, monkeypatch):
    _, staff, _, _, row = setup_restore(approval=approval)
    cancelled = cancel(row, staff)
    assert cancelled.cancelled_at is not None and cancelled.status_before_cancel == expected
    calls = []
    monkeypatch.setattr(services, "notify_event_lifecycle", lambda event, name, registration_id=None: calls.append((name, registration_id)))
    restored = restore_registration(cancelled, actor=staff)
    assert restored.pk == row.pk and restored.created_at == row.created_at
    assert restored.status == expected and restored.cancelled_at is None
    assert restored.status_before_cancel == "" and restored.calendar_sequence > cancelled.calendar_sequence
    assert calls == [("registration_restored", row.pk)]
    assert AuditLog.objects.get(action="event.registration_restored").actor == staff


def test_waitlist_returns_to_original_creation_position_without_intervening_promotion():
    _, staff, event, _, incumbent = setup_restore(capacity=1)
    first = services.register(event, member=account("wait-first"), actor=staff, staff_registration=True)
    second = services.register(event, member=account("wait-second"), actor=staff, staff_registration=True)
    original_created = first.created_at
    restored = restore_registration(cancel(first, staff), actor=staff)
    assert restored.status == "waitlisted" and restored.created_at == original_created
    assert restored.waitlist_position_at is None
    assert _event_registrations(event.makerspace, first.member)[0]["waitlist_position"] == 1
    assert _event_registrations(event.makerspace, second.member)[0]["waitlist_position"] == 2
    cancel(incumbent, staff)
    first.refresh_from_db(); second.refresh_from_db()
    assert (first.status, second.status) == ("registered", "waitlisted")


def test_waitlist_returns_at_tail_when_a_later_waiter_has_been_promoted():
    _, staff, event, _, incumbent = setup_restore(capacity=1)
    early = services.register(event, member=account("early"), actor=staff, staff_registration=True)
    promoted = services.register(event, member=account("promoted"), actor=staff, staff_registration=True)
    last = services.register(event, member=account("last"), actor=staff, staff_registration=True)
    cancelled = cancel(early, staff)
    cancel(incumbent, staff)
    restored = restore_registration(cancelled, actor=staff)
    assert restored.created_at == early.created_at and restored.waitlist_position_at > last.created_at
    assert restored.status == "waitlisted"
    assert _event_registrations(event.makerspace, early.member)[0]["waitlist_position"] == 2
    assert _event_registrations(event.makerspace, last.member)[0]["waitlist_position"] == 1
    cancel(promoted, staff)
    last.refresh_from_db(); early.refresh_from_db()
    assert (last.status, early.status) == ("registered", "waitlisted")


@pytest.mark.parametrize("history", ["pending", "canceled", "paid_offline", "waived"])
def test_any_historical_ledger_row_refuses_undo(history):
    space, staff, _, owner, row = setup_restore()
    cancelled = cancel(row, staff)
    Payment.objects.create(makerspace=space, member=owner, created_by=staff, subject_type="event_registration",
                           subject_id=row.pk, amount=Decimal("1.00"), currency="usd", status=history)
    assert_refusal(cancelled, staff, "historical_charge")


@pytest.mark.parametrize("field,value", [("registration_audience", "invite"), ("discount_amount", Decimal("1.00"))])
def test_consumed_admission_or_discount_refuses_undo(field, value):
    _, staff, _, _, row = setup_restore()
    cancelled = cancel(row, staff)
    setattr(cancelled, field, value); cancelled.save(update_fields=[field])
    assert_refusal(cancelled, staff, "consumed_code")


@pytest.mark.parametrize("kind", ["invite", "promo_code"])
def test_consumed_code_fk_refuses_even_a_free_or_zero_discount_quote(kind):
    from apps.events.models import EventInvite, EventPromoCode
    space, staff, event, _, row = setup_restore()
    cancelled = cancel(row, staff)
    model = EventInvite if kind == "invite" else EventPromoCode
    code = model.objects.create(makerspace=space, event=event, uses=1,
                                **({"percent_off": 100} if kind == "promo_code" else {}))
    setattr(cancelled, kind, code); cancelled.save(update_fields=[kind])
    assert_refusal(cancelled, staff, "consumed_code")
    code.refresh_from_db(); assert code.uses == 1


def test_current_price_that_would_create_debt_refuses_without_money_movement():
    _, staff, event, _, row = setup_restore()
    cancelled = cancel(row, staff)
    event.payment_amount = Decimal("12.00"); event.save(update_fields=["payment_amount"])
    assert_refusal(cancelled, staff, "charge_required")
    assert not Payment.objects.exists()


def test_confirmed_restore_refuses_a_taken_seat():
    _, staff, event, _, row = setup_restore(capacity=1)
    cancelled = cancel(row, staff)
    services.register(event, member=account("replacement"), actor=staff, staff_registration=True)
    assert_refusal(cancelled, staff, "admission_changed")


def test_ticket_capacity_is_enforced_independently_of_event_capacity():
    space, staff, event, owner, row = setup_restore()
    ticket = EventTicketType.objects.create(makerspace=space, event=event, name="Workshop", amount=0, capacity=1)
    row.ticket_type = ticket; row.save(update_fields=["ticket_type"])
    cancelled = cancel(row, staff)
    services.register(event, member=account("ticket-replacement"), actor=staff, staff_registration=True, ticket_type_id=ticket.pk)
    assert_refusal(cancelled, staff, "admission_changed")


@pytest.mark.parametrize("initial,current", [(False, True), (True, False)])
def test_approval_policy_change_refuses_downgrade_or_automatic_confirmation(initial, current):
    _, staff, event, _, row = setup_restore(approval=initial)
    cancelled = cancel(row, staff)
    event.registration_requires_approval = current; event.save(update_fields=["registration_requires_approval"])
    assert_refusal(cancelled, staff, "admission_changed")


@pytest.mark.parametrize("case,reason", [("legacy", "missing_provenance"), ("expired", "window_expired"), ("live", "not_cancelled"), ("cutoff", "registration_closed")])
def test_provenance_window_and_ordinary_cutoff_refusals(case, reason):
    _, staff, event, _, row = setup_restore()
    cancelled = row if case == "live" else cancel(row, staff)
    if case == "legacy":
        cancelled.cancelled_at = None; cancelled.status_before_cancel = ""
        cancelled.save(update_fields=["cancelled_at", "status_before_cancel"])
    elif case == "expired":
        cancelled.cancelled_at = timezone.now() - timedelta(minutes=5)
        cancelled.save(update_fields=["cancelled_at"])
    elif case == "cutoff":
        event.registration_cutoff_at = timezone.now() - timedelta(seconds=1)
        event.save(update_fields=["registration_cutoff_at"])
    assert_refusal(cancelled, staff, reason)


@pytest.mark.django_db(transaction=True)
def test_concurrent_promotion_and_restore_have_one_serializable_fifo_result():
    _, staff, event, _, incumbent = setup_restore(capacity=1)
    early = services.register(event, member=account("race-early"), actor=staff, staff_registration=True)
    later = services.register(event, member=account("race-later"), actor=staff, staff_registration=True)
    cancelled = cancel(early, staff)
    barrier = Barrier(2)

    def transition(restore):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            if restore:
                return restore_registration(EventRegistration.objects.get(pk=cancelled.pk), actor=staff).status
            return cancel(EventRegistration.objects.get(pk=incumbent.pk), staff).status
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(transition, restore) for restore in (False, True)]
        for future in futures:
            future.result(timeout=30)
    early.refresh_from_db(); later.refresh_from_db()
    assert event.registrations.filter(status="registered").count() == 1
    assert {early.status, later.status} == {"registered", "waitlisted"}
    assert early.created_at == cancelled.created_at
    if later.status == "registered":
        assert early.waitlist_position_at > later.created_at


def test_http_restore_requires_manage_registrations_and_returns_provenance():
    from tests.events.staff_grant_helpers import grant_fixture, set_grant_permissions
    space, staff, grantee, event, grant = grant_fixture("edit_details")
    owner = account("restore-grant-owner")
    cancelled = cancel(services.register(event, member=owner, actor=staff, staff_registration=True), staff)
    url = f"/api/v1/admin/event-registrations/{cancelled.pk}/restore/"
    assert client_for(grantee).post(url, {}, format="json").status_code in (403, 404)
    set_grant_permissions(grant, ["manage_registrations"])
    restored = client_for(grantee).post(url, {}, format="json")
    assert restored.status_code == 200 and restored.data["status"] == "registered"
