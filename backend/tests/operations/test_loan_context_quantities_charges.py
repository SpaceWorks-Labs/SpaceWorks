"""Decision 214(d): requested/reserved/outstanding units, utilisation, linked charges and settlements."""
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem
from apps.inventory.availability_projections import outstanding_units, reserved_units
from apps.makerspaces.models import MakerspaceMembership
from apps.operations.reports_loan_context import build_loan_purpose_summary
from apps.operations.reports_loan_context_details import build_event_equipment
from apps.payments.models import ManualSettlement, Payment
from tests.operations.test_loan_context_metrics import setup_metrics
from tests.test_request_workflow import make_hardware_request, make_member

pytestmark = pytest.mark.django_db


def _charge(request, subject_type, status, amount="10.00", currency="inr"):
    return Payment.objects.create(
        makerspace=request.makerspace, member=request.requester, created_by=request.requester,
        subject_type=subject_type, subject_id=request.pk, amount=amount, currency=currency, status=status)


def _by_context(result, field):
    totals = {}
    for row in result.records:
        totals[row["context"]] = totals.get(row["context"], 0) + row[field]
    return totals


def test_quantities_come_from_the_projections_and_utilisation_is_issued_over_requested():
    space, actor, product, requests, event, booking = setup_metrics("lcq-quantities")
    result = build_loan_purpose_summary(space.pk, actor=actor)
    assert _by_context(result, "requested_units") == {
        "Ordinary loan": 1, "Event": 1, "Booking": 1, "Event and booking": 3}
    assert _by_context(result, "outstanding_units") == {
        "Ordinary loan": 1, "Event": 1, "Booking": 1, "Event and booking": 2}
    # A loan that was issued holds nothing in reserve.
    assert sum(row["reserved_units"] for row in result.records) == 0
    both = next(row for row in result.records if row["context"] == "Event and booking")
    assert both["utilisation"] == 1.0
    rows = {row["request_id"]: row for row in build_event_equipment(
        space.pk, actor=actor, subject_kind="event", subject_id=event.pk).records}
    both_request = HardwareRequest.objects.prefetch_related("items").get(pk=requests[3].pk)
    assert rows[requests[3].pk]["outstanding_units"] == outstanding_units(both_request) == 2
    assert rows[requests[3].pk]["requested_units"] == 3


def test_partly_lent_ask_has_utilisation_below_one_and_accepted_request_holds_reserve():
    space, actor, product, requests, event, booking = setup_metrics("lcq-partial")
    HardwareRequestItem.objects.filter(request=requests[0]).update(requested_quantity=4, accepted_quantity=4)
    result = build_loan_purpose_summary(space.pk, actor=actor)
    ordinary = next(row for row in result.records if row["context"] == "Ordinary loan")
    assert ordinary["requested_units"] == 4 and ordinary["utilisation"] == 0.25
    waiting = make_hardware_request(space, product, quantity=3, status=HardwareRequest.Status.ACCEPTED)
    HardwareRequestItem.objects.filter(request=waiting).update(accepted_quantity=3)
    waiting = HardwareRequest.objects.prefetch_related("items").get(pk=waiting.pk)
    assert reserved_units(waiting) == 3
    waiting.status = HardwareRequest.Status.ISSUED
    assert reserved_units(waiting) == 0


def test_charges_and_settlements_join_the_loan_once_across_both_contexts():
    space, actor, product, requests, event, booking = setup_metrics("lcq-charges")
    both = HardwareRequest.objects.get(pk=requests[3].pk)
    _charge(both, Payment.SubjectType.LOAN_DEPOSIT, Payment.Status.PENDING, "20.00")
    paid = _charge(both, Payment.SubjectType.LOAN_LATE_FEE, Payment.Status.PAID_OFFLINE, "5.00")
    ManualSettlement.objects.create(payment=paid, amount="5.00", currency="inr", method="cash",
                                    received_at=timezone.now(), recorded_by=actor)
    _charge(both, Payment.SubjectType.LOAN_RENTAL, Payment.Status.CANCELED, "99.00")
    result = build_loan_purpose_summary(space.pk, actor=actor)
    assert result.meta["charges_available"] is True
    assert _by_context(result, "charge_count") == {"Ordinary loan": 0, "Event": 0, "Booking": 0, "Event and booking": 2}
    row = next(row for row in result.records if row["context"] == "Event and booking")
    assert (row["charge_currency"], row["charge_pending_amount"], row["charge_paid_amount"],
            row["settlement_count"]) == ("inr", Decimal("20.00"), Decimal("5.00"), 1)
    detail = {r["request_id"]: r for r in build_event_equipment(
        space.pk, actor=actor, subject_kind="event", subject_id=event.pk).records}
    assert detail[both.pk]["charge_count"] == 2 and detail[both.pk]["settlement_count"] == 1
    assert detail[requests[1].pk]["charge_count"] == 0


def test_two_currencies_on_one_loan_are_labelled_mixed_not_summed():
    space, actor, product, requests, event, booking = setup_metrics("lcq-mixed")
    both = HardwareRequest.objects.get(pk=requests[3].pk)
    _charge(both, Payment.SubjectType.LOAN_DEPOSIT, Payment.Status.PENDING, "20.00", "inr")
    _charge(both, Payment.SubjectType.LOAN_LATE_FEE, Payment.Status.PENDING, "5.00", "usd")
    row = next(row for row in build_loan_purpose_summary(space.pk, actor=actor).records
               if row["context"] == "Event and booking")
    assert row["charge_currency"] == "mixed" and row["charge_count"] == 2
    assert row["charge_pending_amount"] == Decimal("0")


def test_reader_without_finance_sees_loans_but_no_money():
    space, actor, product, requests, event, booking = setup_metrics("lcq-no-finance")
    _charge(HardwareRequest.objects.get(pk=requests[3].pk), Payment.SubjectType.LOAN_DEPOSIT,
            Payment.Status.PENDING)
    inventory = make_member("lcq-inventory", space, membership_role=MakerspaceMembership.Role.INVENTORY_MANAGER,
                            role=User.Role.REQUESTER)
    result = build_loan_purpose_summary(space.pk, actor=inventory)
    assert result.meta["charges_available"] is False
    assert sum(row["charge_count"] for row in result.records) == 0
    assert sum(row["requested_units"] for row in result.records) == 6
