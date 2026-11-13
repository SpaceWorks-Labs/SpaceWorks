"""The fixed Event Manager collects registration fees without finance authority.

Event Manager holds ONLY manage_events (no view_finance, record_payment or view_audit).
With the online rail off, paid registrations become pending charges the Event Manager
settles by hand -- through the same reconciliation service and ManualSettlement receipt
as finance staff -- and nothing outside event registrations becomes visible to them.
"""
from decimal import Decimal
from unittest.mock import Mock

import pytest

from apps.accounts import rbac
from apps.audit.models import AuditLog
from apps.events import services as event_services
from apps.payments.availability import online_payments_enabled
from apps.payments.models import ManualSettlement, Payment
from apps.payments.resolution import resolve_payment_source
from tests.fixed_roles.helpers import assign_builtin_roles
from tests.payments.test_track3_booking_event_charging import (
    bookable, create_booking, member_with_phone, published_event,
)
from tests.return_helpers import authenticated_client, make_space, make_user, settlement_payload

pytestmark = pytest.mark.django_db

CASH_ONLY = ["charges.enabled", "charges.events", "charges.bookings"]


def _space(slug, features=CASH_ONLY):
    space = make_space(slug)
    space.enabled_features = list(features)
    space.save(update_fields=["enabled_features", "updated_at"])
    return space


def _actor(space, slug, name):
    user = make_user(f"{space.slug}-{name}", access_status="active", account_kind="member" if slug == "member" else "staff",
                     staff_makerspace=None if slug == "member" else space)
    assign_builtin_roles(user, space, slug)
    return user


def _paid_registration(space, name="attendee"):
    host = member_with_phone(f"{space.slug}-host-{name}", space)
    event = published_event(space, host)
    member = member_with_phone(f"{space.slug}-{name}", space)
    return event_services.register(event, member=member, actor=None)


def _event_charge(space, name="attendee"):
    registration = _paid_registration(space, name)
    return Payment.objects.get(
        makerspace=space, subject_type=Payment.SubjectType.EVENT_REGISTRATION,
        subject_id=registration.pk,
    )


def _booking_charge(space):
    member = member_with_phone(f"{space.slug}-booker", space)
    booking = create_booking(bookable(space), member)
    return Payment.objects.get(
        makerspace=space, subject_type=Payment.SubjectType.BOOKING, subject_id=booking.pk,
    )


def _list(client, space, query=""):
    return client.get(f"/api/v1/admin/makerspace/{space.pk}/payments{query}")


def test_event_manager_holds_no_finance_action():
    space = _space("em-pay-actions")
    actor = _actor(space, "event_manager", "em")
    assert rbac.can(actor, rbac.Action.MANAGE_EVENTS, space.pk)
    for action in (rbac.Action.VIEW_FINANCE, rbac.Action.RECORD_PAYMENT, rbac.Action.VIEW_AUDIT):
        assert not rbac.can(actor, action, space.pk)


@pytest.mark.parametrize("for_recording", [False, True])
def test_event_manager_lists_only_event_registration_payments(for_recording):
    space = _space(f"em-pay-list-{int(for_recording)}")
    event_payment = _event_charge(space)
    _booking_charge(space)
    client = authenticated_client(_actor(space, "event_manager", "em"))
    query = "?subject_type=event_registration" + ("&for_recording=true" if for_recording else "")

    response = _list(client, space, query)

    assert response.status_code == 200, response.data
    assert [row["id"] for row in response.data["results"]] == [event_payment.pk]
    assert {row["subject_type"] for row in response.data["results"]} == {"event_registration"}


@pytest.mark.parametrize("query", ["", "?subject_type=booking", "?subject_type=makerspace_membership",
                                   "?for_recording=true"])
def test_event_manager_cannot_list_other_money(query):
    space = _space("em-pay-other")
    _event_charge(space)
    _booking_charge(space)
    client = authenticated_client(_actor(space, "event_manager", "em"))
    assert _list(client, space, query).status_code in (403, 404)


def test_event_manager_cannot_list_another_makerspace():
    home = _space("em-pay-home")
    foreign = _space("em-pay-foreign")
    _event_charge(foreign)
    client = authenticated_client(_actor(home, "event_manager", "em"))
    assert _list(client, foreign, "?subject_type=event_registration").status_code == 404


def test_member_cannot_list_or_settle_event_payments():
    space = _space("em-pay-member")
    payment = _event_charge(space)
    actor = _actor(space, "member", "plain")
    client = authenticated_client(actor)
    base = f"/api/v1/admin/makerspace/{space.pk}/payments"
    assert _list(client, space, "?subject_type=event_registration").status_code in (403, 404)
    assert client.post(f"{base}/{payment.pk}/mark-offline", settlement_payload(), format="json").status_code in (403, 404)
    assert client.post(f"{base}/{payment.pk}/waive", format="json").status_code in (403, 404)
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PENDING
    assert not ManualSettlement.objects.filter(payment=payment).exists()
    assert not AuditLog.objects.filter(actor=actor, makerspace=space).exists()


def test_event_manager_marks_paid_offline_with_receipt_and_waives():
    space = _space("em-pay-settle")
    paid = _event_charge(space, "payer")
    waived = _event_charge(space, "waived")
    actor = _actor(space, "event_manager", "em")
    client = authenticated_client(actor)
    base = f"/api/v1/admin/makerspace/{space.pk}/payments"

    settled = client.post(f"{base}/{paid.pk}/mark-offline",
                          settlement_payload(method="upi", reference="UPI-778"), format="json")
    assert settled.status_code == 200, settled.data
    assert settled.data["status"] == Payment.Status.PAID_OFFLINE
    receipt = ManualSettlement.objects.get(payment=paid)
    assert (receipt.method, receipt.reference, receipt.recorded_by) == ("upi", "UPI-778", actor)
    assert receipt.amount == paid.amount
    assert AuditLog.objects.filter(actor=actor, action="payment.paid_offline", target_id=str(paid.pk)).exists()

    response = client.post(f"{base}/{waived.pk}/waive", format="json")
    assert response.status_code == 200, response.data
    waived.refresh_from_db()
    assert waived.status == Payment.Status.WAIVED
    assert not ManualSettlement.objects.filter(payment=waived).exists()
    assert AuditLog.objects.filter(actor=actor, action="payment.waived", target_id=str(waived.pk)).exists()


def test_event_manager_cannot_settle_a_booking_charge():
    space = _space("em-pay-booking")
    booking = _booking_charge(space)
    client = authenticated_client(_actor(space, "event_manager", "em"))
    base = f"/api/v1/admin/makerspace/{space.pk}/payments"
    assert client.post(f"{base}/{booking.pk}/mark-offline", settlement_payload(), format="json").status_code == 403
    assert client.post(f"{base}/{booking.pk}/waive", format="json").status_code == 403
    booking.refresh_from_db()
    assert booking.status == Payment.Status.PENDING


def test_rail_off_records_a_pending_cash_charge_without_checkout(monkeypatch):
    space = _space("em-pay-rail-off")
    checkout = Mock()
    monkeypatch.setattr("apps.events.service_payments._schedule_checkout", checkout)
    payment = _event_charge(space)
    assert not online_payments_enabled(space, "events")
    assert payment.status == Payment.Status.PENDING
    assert payment.amount == Decimal("8.00")
    if resolve_payment_source(space) is None:
        # No gateway at all: the debt waits, unclaimed, for a desk receipt.
        assert payment.provider == Payment.Provider.UNCLAIMED
    checkout.assert_not_called()


def test_rail_on_schedules_provider_checkout(monkeypatch):
    space = _space("em-pay-rail-on")
    monkeypatch.setattr("apps.events.service_payments.online_payments_enabled", lambda *_args: True)
    checkout = Mock()
    monkeypatch.setattr("apps.events.service_payments._schedule_checkout", checkout)
    payment = _event_charge(space)
    assert payment.status == Payment.Status.PENDING
    checkout.assert_called_once_with(payment)


def test_charge_tracking_off_registers_for_free():
    space = _space("em-pay-free", features=[])
    registration = _paid_registration(space)
    assert registration.status == "registered"
    assert not Payment.objects.filter(makerspace=space).exists()
