"""E-B6 C18/B20: an approved refund can cancel the tickets it paid for; a refused refund tells staff.

Real services and a real database. Cancelling is idempotent, never refunds more than staff approved, is refused
when the switch is off or the charge is not an event ticket, and the failed-refund notice reaches staff only.
"""
from decimal import Decimal

import pytest

from apps.audit.models import AuditLog
from apps.events.models import EventOrder, EventRegistration
from apps.payments.exceptions_refunds import RefundNotAllowed
from apps.payments.models import Payment, Refund, RefundCase
from apps.payments.services_refund_cases import mark_approval_failed, open_due_case
from apps.payments.services_refund_decisions import approve_case
from tests.events.orders_helpers import L6_FEATURES, order_payment, place, settle_offline, ticketed_event, verified
from tests.payments.refund_case_helpers import charge, member, paid_event, receipt, registration, space_with_currency

pytestmark = pytest.mark.django_db


def paid_two_seat_order(capture, *, switch=True):
    space, event, staff, ticket = ticketed_event(amount=12)
    if switch:
        space.enabled_features = sorted(set(space.enabled_features) | {"events.refund_cancels_tickets"})
        space.save(update_fields=["enabled_features"])
    buyer = verified("buyer")
    assert place(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 2}]).status_code == 201
    order = EventOrder.objects.get()
    with capture(execute=True):
        settle_offline(order_payment(order), staff)
    payment = order_payment(order)
    case = RefundCase.objects.create(payment=payment, kind="request", area="events", reason_code="member_request",
                                     requested_by=buyer)
    return space, event, staff, order, payment, case


def test_approval_cancels_every_seat_and_refunds_only_what_was_approved(django_capture_on_commit_callbacks):
    space, event, staff, order, payment, case = paid_two_seat_order(django_capture_on_commit_callbacks)
    with django_capture_on_commit_callbacks(execute=True):
        approve_case(case, actor=staff, amount=Decimal("10.00"), receipt=receipt(), cancel_tickets=True)
    assert set(EventRegistration.objects.filter(event=event).values_list("status", flat=True)) == {"cancelled"}
    assert set(order.seats.values_list("status", flat=True)) == {"void"}
    # The seats were voided before the registrations were cancelled, so no second refund share opened.
    assert Refund.objects.get().amount == Decimal("10.00")
    assert RefundCase.objects.filter(payment=payment).count() == 1
    # Two seats, one registration behind them (the buyer's; the second seat is unclaimed): one registration cancelled.
    assert AuditLog.objects.filter(action="payment.refund_case_tickets_cancelled", meta__cancelled=1).exists()


def test_cancelling_twice_changes_nothing(django_capture_on_commit_callbacks):
    from apps.events.orders_cancel import cancel_tickets_for_refund
    space, event, staff, order, payment, case = paid_two_seat_order(django_capture_on_commit_callbacks)
    with django_capture_on_commit_callbacks(execute=True):
        approve_case(case, actor=staff, amount=Decimal("10.00"), receipt=receipt(), cancel_tickets=True)
    with django_capture_on_commit_callbacks(execute=True):
        assert cancel_tickets_for_refund(payment, actor=staff) == []
    assert EventRegistration.objects.filter(event=event, status="cancelled").count() == 1
    assert set(order.seats.values_list("status", flat=True)) == {"void"}


def test_refused_while_the_switch_is_off_and_nothing_moves(django_capture_on_commit_callbacks):
    space, event, staff, order, payment, case = paid_two_seat_order(django_capture_on_commit_callbacks, switch=False)
    with pytest.raises(RefundNotAllowed) as refused:
        approve_case(case, actor=staff, receipt=receipt(), cancel_tickets=True)
    assert refused.value.detail["code"] == "refund_cancel_tickets_unavailable"
    assert not Refund.objects.exists() and RefundCase.objects.get(pk=case.pk).status == "open"
    assert EventRegistration.objects.filter(event=event, status="registered").exists()


def test_refused_for_a_charge_that_is_not_an_event_ticket():
    space = space_with_currency("c18-nonevent")
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"events"})  # the feature's parent module
    space.enabled_features = sorted(set(space.enabled_features) | {"events.ticket_types", *L6_FEATURES, "events.refund_cancels_tickets"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    user = member("c18-nonevent-m", space)
    from apps.makerspaces.models import MakerspaceMembership
    membership = MakerspaceMembership.objects.get(makerspace=space, user=user)
    payment = charge(space, user, subject_type=Payment.SubjectType.MAKERSPACE_MEMBERSHIP, subject_id=membership.pk)
    case = RefundCase.objects.create(payment=payment, kind="request", area="membership",
                                     reason_code="member_request", requested_by=user)
    with pytest.raises(RefundNotAllowed) as refused:
        approve_case(case, actor=user, receipt=receipt(), cancel_tickets=True)
    assert refused.value.detail["code"] == "refund_cancel_tickets_not_event"


def test_the_failed_refund_notice_reaches_staff_only(django_capture_on_commit_callbacks):
    from apps.payments.notifications_refund_cases import EVENTS, MEMBER_EVENTS, STAFF_EVENTS, case_revision
    assert "refund_approval_failed" in STAFF_EVENTS and "refund_approval_failed" not in MEMBER_EVENTS
    assert "refund_approval_failed" in EVENTS
    space = space_with_currency("b20-staff")
    user = member("b20-m", space)
    payment = charge(space, user, subject_id=registration(paid_event(space), user).pk, status="paid_online",
                     provider="stripe", stripe_payment_intent_id="pi_b20")
    case = open_due_case(payment, reason_code="event_cancelled", actor=None)
    refund = Refund.objects.create(payment=payment, amount=Decimal("5.00"), currency="usd", provider="stripe",
                                   status="failed", created_by=user)
    RefundCase.objects.filter(pk=case.pk).update(status="approved", refund=refund)
    case.refresh_from_db()
    with django_capture_on_commit_callbacks(execute=True):
        mark_approval_failed([case], refund, actor=None)
    case.refresh_from_db()
    assert case.status == "approval_failed"
    assert AuditLog.objects.filter(action="payment.refund_case_approval_failed").exists()
    before = case_revision(case, "refund_approval_failed")
    # A second refused attempt is a different revision, so staff hear about it again.
    other = Refund.objects.create(payment=payment, amount=Decimal("5.00"), currency="usd", provider="stripe",
                                  status="failed", created_by=user)
    RefundCase.objects.filter(pk=case.pk).update(refund=other)
    case.refresh_from_db()
    assert case_revision(case, "refund_approval_failed") != before
