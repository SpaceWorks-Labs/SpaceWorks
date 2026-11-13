"""Flow audit (decisions 214-218): a loan linked to an event and/or a booking outlives both of them.

The plan's lifecycle rule is that cancelling the event or the booking after issue never erases or
auto-settles the loan: the borrower stays accountable until a real return or an explicit loss/damage
resolution, the link rows are retained as history, switching Events/Bookings off then on again changes
nothing by itself, and the money for a damaged return is raised exactly once by the loan domain.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.bookings import services_transitions
from apps.bookings.models import Booking
from apps.bookings.models_loan_context import BookingLoanContext
from apps.events import services
from apps.events.models import Event
from apps.events.models_loan_context import EventLoanContext
from apps.hardware_requests import workflow
from apps.hardware_requests.models import HardwareRequest, RequesterAccountability
from apps.payments.models import Payment
from tests.encryption.conftest import enabled_encryption
from tests.events.test_booking_decision_replacement import linked
from tests.fixed_roles.helpers import staff_account
from tests.hardware_requests.test_loan_damage_lost import url as charge_url
from tests.hardware_requests.test_loan_payments import quiet_storage_and_stripe  # noqa: F401
from apps.makerspaces.module_install import uninstall_module
from tests.module_helpers import disable_module
from tests.payments.pricing.helpers import D, client, pricing_space, rate
from tests.return_helpers import make_issued_request, make_product, make_return_evidence

pytestmark = pytest.mark.django_db(transaction=True)


def _lending_on(space):
    space.enabled_modules = sorted(set(space.enabled_modules) | {"request_workflow", "events"})
    space.enabled_features = sorted(set(space.enabled_features or []) | {"loans.enabled"})
    space.save(update_fields=["enabled_modules", "enabled_features"])


def _both_contexts_loan(slug):
    """An ISSUED loan linked to a published event AND a pending booking of the same space."""
    space, staff, _member, event, _room, booking, _decision, _client = linked(slug)
    _lending_on(space)
    Event.objects.filter(pk=event.pk).update(status=Event.Status.PUBLISHED)
    request = make_issued_request(space, staff, [(make_product(space), 2)])
    EventLoanContext.objects.create(makerspace=space, request=request, event=event, active=True)
    BookingLoanContext.objects.create(makerspace=space, request=request, booking=booking, active=True, revision=1)
    return space, staff, Event.objects.get(pk=event.pk), booking, request


def _return_everything(space, staff, request):
    item = request.items.get()
    workflow.return_items(staff, request, make_return_evidence(space, staff).pk, "Checked and counted.",
                          request.assigned_box.code,
                          [{"item_id": item.pk, "returned": item.issued_quantity, "damaged": 0, "missing": 0}])
    return HardwareRequest.objects.get(pk=request.pk)


def _contexts(request):
    return (EventLoanContext.objects.filter(request=request, active=True).count(),
            BookingLoanContext.objects.filter(request=request, active=True).count())


def test_cancelling_the_event_and_the_booking_after_issue_leaves_the_loan_issued_and_returnable():
    space, staff, event, booking, request = _both_contexts_loan("fa-cancel")
    with enabled_encryption():
        services.cancel(event, actor=staff)
        services_transitions.cancel_booking(Booking.objects.get(pk=booking.pk), actor=staff)
    assert Event.objects.get(pk=event.pk).status == Event.Status.CANCELLED
    assert Booking.objects.get(pk=booking.pk).status == Booking.Status.CANCELLED
    # The borrower is still accountable: nothing returned, settled or released the stock behind their back.
    loan = HardwareRequest.objects.get(pk=request.pk)
    assert loan.status == HardwareRequest.Status.ISSUED
    assert not RequesterAccountability.objects.filter(request=request).exists()
    assert _contexts(request) == (1, 1)
    returned = _return_everything(space, staff, request)
    assert returned.status == HardwareRequest.Status.RETURNED
    assert _contexts(request) == (1, 1)  # retained as history after the real return


def test_switching_events_and_bookings_off_and_on_replays_nothing_and_keeps_the_loan_and_links():
    space, staff, event, booking, request = _both_contexts_loan("fa-offon")
    payments_before = Payment.objects.filter(makerspace=space).count()
    disable_module(space, "events")
    disable_module(space, "bookings")
    assert HardwareRequest.objects.get(pk=request.pk).status == HardwareRequest.Status.ISSUED
    assert _contexts(request) == (1, 1)
    # Return stays reachable while the contextual modules are off (the workflow module owns it).
    assert _return_everything(space, staff, request).status == HardwareRequest.Status.RETURNED
    space.refresh_from_db()
    space.enabled_modules = sorted(set(space.enabled_modules) | {"events", "bookings"})
    space.save(update_fields=["enabled_modules"])
    assert _contexts(request) == (1, 1)
    assert Payment.objects.filter(makerspace=space).count() == payments_before
    assert Booking.objects.get(pk=booking.pk).status == Booking.Status.PENDING  # no automatic rebooking
    assert Event.objects.get(pk=event.pk).status == Event.Status.PUBLISHED


def test_a_damaged_event_linked_loan_raises_one_loan_charge_without_any_payment_rail(
        django_capture_on_commit_callbacks, quiet_storage_and_stripe):  # noqa: F811
    space, manager = pricing_space("fa-damage")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"events", "request_workflow"})
    space.save(update_fields=["enabled_modules"])
    uninstall_module(space, "payments")  # tracking stays on, the online rail is gone
    space.refresh_from_db()
    assert "payments.enabled" not in space.enabled_features and "charges.loans" in space.enabled_features
    rate(space, "loans", damage="12.00")
    staff = staff_account(space, "fa-damage-staff", "space_manager")
    ends = timezone.now() + timedelta(days=1)
    event = Event.objects.create(makerspace=space, title="Demo day", starts_at=ends - timedelta(hours=3),
                                 ends_at=ends, status=Event.Status.PUBLISHED)
    request = make_issued_request(space, staff, [(make_product(space, unit_cost=Decimal("40")), 1)])
    EventLoanContext.objects.create(makerspace=space, request=request, event=event, active=True)
    item = request.items.get()
    with django_capture_on_commit_callbacks(execute=True):
        workflow.return_items(staff, request, make_return_evidence(space, staff).pk, "Cracked case.",
                              request.assigned_box.code,
                              [{"item_id": item.pk, "returned": 0, "damaged": 1, "missing": 0}])
    row = RequesterAccountability.objects.get(request=request)
    reply = client(staff).post(charge_url(space, request, row), {"amount": "15.00"}, format="json")
    assert reply.status_code == 200, reply.data
    payment = Payment.objects.get(subject_type="loan_damage", subject_id=row.pk)
    assert payment.amount == D("15.00") and payment.member_id == request.requester_id
    assert payment.provider == "unclaimed"  # recorded as money owed; no gateway claimed it
    # Cancelling the event afterwards neither removes the debt nor the link.
    with enabled_encryption():
        services.cancel(event, actor=staff)
    assert Payment.objects.filter(subject_type="loan_damage", subject_id=row.pk).count() == 1
    assert EventLoanContext.objects.get(request=request).active is True
