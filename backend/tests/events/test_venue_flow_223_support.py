"""Decision 223 (h) (m) G5, the consumables report and decision 159(2)."""
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.bookings import services_bookings
from apps.bookings.event_host_guard import BookingHostsEvent
from apps.bookings.models import Booking
from apps.bookings.models_included_hours import IncludedHoursUsage
from apps.events import equipment_window
from apps.evidence.storage import EvidenceValidationResult
from apps.events.models import Event
from apps.hardware_requests.loan_charges_common import fee_exempt
from apps.operations.reports_consumable_context import _planned
from apps.payments.models import MakerspacePaymentSettings, Payment
from apps.presence.guard import MemberPresenceRequired, PresenceRequired, WaiverAcceptanceRequired
from tests.encryption.conftest import enabled_encryption
from tests.events.orders_helpers import l6_space, make_staff
from tests.events.test_booking_decision_replacement import linked
from tests.hardware_requests.test_loan_payments import accepted_loan, issue, loan_payment, loan_space
from tests.payments.test_track3_booking_event_charging import bookable

pytestmark = pytest.mark.django_db(transaction=True)


# --- (h) house booking ---------------------------------------------------------------------------

def house_room(slug, approval_mode="approve"):
    maker = l6_space(slug)
    maker.enabled_modules = sorted(set(maker.enabled_modules) | {"bookings"})
    maker.enabled_features = sorted(set(maker.enabled_features) | {"charges.enabled", "charges.bookings"})
    maker.save(update_fields=["enabled_modules", "enabled_features"])
    return maker, make_staff(maker), bookable(maker, approval_mode=approval_mode, amount="40.00")


def test_house_booking_has_no_member_no_charge_and_is_confirmed_even_in_an_approval_room():
    maker, staff, room = house_room("house-service")
    start = timezone.now() + timedelta(days=3)
    with enabled_encryption():
        booking = services_bookings.create_booking(room, starts_at=start, ends_at=start + timedelta(hours=2),
                                                   actor=staff, house=True)
    assert booking.is_house and booking.member_id is None
    assert booking.status == Booking.Status.CONFIRMED and booking.pricing_snapshot == {}
    assert not Payment.objects.filter(makerspace=maker, subject_type="booking", subject_id=booking.pk).exists()
    assert not IncludedHoursUsage.objects.filter(booking=booking).exists()  # consumes no plan hours (221(d))
    assert AuditLog.objects.filter(action="booking.house_created", target_id=str(booking.pk)).exists()


def test_house_booking_needs_manage_reservations_and_refuses_a_member():
    from django.core.exceptions import PermissionDenied as DjangoDenied
    from rest_framework.exceptions import PermissionDenied, ValidationError
    maker, staff, room = house_room("house-guard")
    member = SimpleNamespace(pk=1)
    start = timezone.now() + timedelta(days=3)
    with pytest.raises(ValidationError):
        services_bookings.create_booking(room, starts_at=start, ends_at=start + timedelta(hours=1),
                                         actor=staff, house=True, member=member)
    outsider = make_staff(l6_space("house-guard-other"), username="outsider")
    with enabled_encryption(), pytest.raises((PermissionDenied, DjangoDenied, Exception)):
        services_bookings.create_booking(room, starts_at=start, ends_at=start + timedelta(hours=1),
                                         actor=outsider, house=True)


def test_house_flag_cannot_sit_on_a_member_booking():
    maker, staff, room = house_room("house-constraint")
    start = timezone.now() + timedelta(days=3)
    with enabled_encryption():
        booking = services_bookings.create_booking(room, starts_at=start, ends_at=start + timedelta(hours=1),
                                                   actor=staff, house=True)
    with pytest.raises(IntegrityError), transaction.atomic():
        Booking.objects.filter(pk=booking.pk).update(member=staff)


def test_staff_create_endpoint_accepts_house_true_without_a_member_id():
    maker, staff, room = house_room("house-api")
    client = APIClient()
    client.force_authenticate(staff)
    start = timezone.now() + timedelta(days=4)
    body = {"starts_at": start.isoformat(), "ends_at": (start + timedelta(hours=1)).isoformat(), "house": True}
    with enabled_encryption():
        response = client.post(reverse("admin-space-booking-list", kwargs={"pk": room.pk}), body, format="json")
        both = client.post(reverse("admin-space-booking-list", kwargs={"pk": room.pk}),
                           {**body, "member_id": staff.pk}, format="json")
        neither = client.post(reverse("admin-space-booking-list", kwargs={"pk": room.pk}),
                              {k: v for k, v in body.items() if k != "house"}, format="json")
    assert response.status_code == 201, response.data
    assert response.data["is_house"] is True and response.data["status"] == "confirmed"
    assert both.status_code == 400 and neither.status_code == 400


# --- (m) the booker is told the room hosts an event ------------------------------------------------

def test_member_cancelling_an_event_room_must_confirm_first():
    maker, staff, member, event, room, booking, _decision, _client = linked("m-booker-cancel")
    with enabled_encryption():
        with pytest.raises(BookingHostsEvent) as asked:
            services_bookings.cancel_booking(booking, actor=member, member_cancel=True)
        assert asked.value.detail["code"] == "booking_hosts_event"
        assert asked.value.detail["event"]["kind"] in ("event", "reserved")
        booking.refresh_from_db()
        assert booking.status == Booking.Status.PENDING
        cancelled = services_bookings.cancel_booking(booking, actor=member, member_cancel=True,
                                                     confirm_event_room=True)
    assert cancelled.status == Booking.Status.CANCELLED
    assert AuditLog.objects.filter(action="booking.cancelled_event_room_confirmed").exists()


def test_member_cancelling_an_ordinary_booking_needs_no_confirmation():
    maker, staff, member, event, room, _booking, _decision, _client = linked("m-booker-plain")
    start = event.starts_at + timedelta(days=6)
    with enabled_encryption():
        plain = services_bookings.create_booking(room, starts_at=start, ends_at=start + timedelta(hours=1),
                                                 member=member, actor=member)
        assert services_bookings.cancel_booking(plain, actor=member, member_cancel=True).status == "cancelled"


def test_my_bookings_lists_the_event_label_on_a_hosting_booking():
    from apps.bookings.serializers_member import MemberBookingSerializer
    maker, staff, member, event, room, booking, _decision, _client = linked("m-booker-label")
    with enabled_encryption():
        data = MemberBookingSerializer(booking, context={}).data
    assert data["hosts_event"]["kind"] in ("event", "reserved")


# --- G5 bulk planning reports each refusal per row ------------------------------------------------

@pytest.mark.parametrize("refusal,code", [
    (PresenceRequired(), "presence_required"),
    (MemberPresenceRequired(), "membership_required"),
    (WaiverAcceptanceRequired(), "waiver_acceptance_required"),
])
def test_bulk_planning_reports_a_presence_or_membership_refusal_per_row(monkeypatch, refusal, code):
    maker, staff, _member, event, _room, _booking, _decision, _client = linked("g5-" + code)
    monkeypatch.setattr(equipment_window, "window_rows", lambda *a, **k: ([], {}, {}))
    monkeypatch.setattr(equipment_window, "_totals", lambda *a, **k: [])
    seen = []

    def fake_create_pending(**kwargs):
        seen.append(kwargs["event_registration_id"])
        if kwargs["event_registration_id"] == 1:
            raise refusal
        return "request", SimpleNamespace(pk=77, status="pending"), False

    monkeypatch.setattr("apps.hardware_requests.contextual_equipment_service.create_pending", fake_create_pending)
    lines = [{"product_id": 5, "quantity": 1}]
    people = [{"registration_id": 1, "lines": None}, {"registration_id": 2, "lines": None}]
    with enabled_encryption():
        result = equipment_window.plan_for_participants(
            staff, event, operation_id=uuid4(), requested_for=None, lines=lines, participants=people, dry_run=False)
    assert seen == [1, 2]  # the second participant is still planned
    assert result["results"][0] == {"registration_id": 1, "outcome": "error", "code": code}
    assert result["results"][1]["outcome"] == "created"


# --- consumables report: per-person quantity times participants ---------------------------------------

class FakeRows:
    def __init__(self, rows):
        self.rows = rows

    def values_list(self, *fields):
        return self.rows


def test_planned_quantity_multiplies_a_shared_row_by_its_participants():
    line = {"kind": "consumable", "product_id": 7, "quantity_per_person": 3}
    rows = FakeRows([(1, [line]), (2, [line])])
    assert _planned(rows) == {7: 6}  # two single-person rows
    assert _planned(rows, {1: 10}) == {7: 33}  # row 1 is shared by 10 people: 30 + 3


def test_planned_quantity_ignores_a_zero_participant_count_and_non_consumables():
    rows = FakeRows([(1, [{"kind": "returnable", "product_id": 7, "quantity_per_person": 4},
                          {"kind": "consumable", "product_id": 8, "quantity_per_person": 2}])])
    assert _planned(rows, {1: 0}) == {8: 2}


# --- decision 159(2): no fees on account-less walk-in loans -----------------------------------------

def test_fee_exempt_for_walk_in_and_not_for_a_member():
    assert fee_exempt(SimpleNamespace(requester=SimpleNamespace(is_walk_in=True, pk=1))) is True
    assert fee_exempt(SimpleNamespace(requester=SimpleNamespace(is_walk_in=False, pk=None))) is False


def test_walk_in_loan_raises_no_deposit_but_an_account_loan_does(django_capture_on_commit_callbacks, monkeypatch):
    monkeypatch.setattr("apps.evidence.storage.finalize_upload",
                        lambda evidence, max_bytes: EvidenceValidationResult(size=123, content_type="image/png"))
    monkeypatch.setattr("apps.payments.services_checkout.create_checkout_url", lambda *a, **k: "")
    makerspace, staff = loan_space("walk-in-fees", loan_deposit_mode=MakerspacePaymentSettings.LoanDepositMode.FIXED,
                                   loan_deposit_amount=Decimal("5.00"))
    walk_in_loan = accepted_loan(makerspace, staff)
    walk_in_loan.requester.is_walk_in = True
    walk_in_loan.requester.save(update_fields=["is_walk_in"])
    account_loan = accepted_loan(makerspace, staff)
    issue(staff, walk_in_loan, django_capture_on_commit_callbacks)
    issue(staff, account_loan, django_capture_on_commit_callbacks)
    assert loan_payment(walk_in_loan, Payment.SubjectType.LOAN_DEPOSIT) is None
    assert loan_payment(account_loan, Payment.SubjectType.LOAN_DEPOSIT) is not None
