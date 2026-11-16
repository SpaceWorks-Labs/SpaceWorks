"""Lane L15 (A14): staff waive loan fees -- append-only, pending -> waived, paid -> refund case."""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, InternalError, connection, transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.payments.models import LoanFeeWaiver, Payment, RefundCase
from apps.payments.pricing import quote
from tests.fixed_roles.helpers import staff_account
from tests.hardware_requests.test_loan_payments import quiet_storage_and_stripe  # noqa: F401
from tests.payments.pricing.helpers import D, client, pricing_space, rate, switch
from tests.return_helpers import make_issued_request, make_product

pytestmark = pytest.mark.django_db


@pytest.fixture
def loan():
    space, _ = pricing_space("waive", loan_deposit_mode="fixed", loan_deposit_amount=D("10.00"))
    staff = staff_account(space, "waive-staff", "space_manager")
    rate(space, "loans", rental_per_day="2.00")
    request = make_issued_request(space, staff, [(make_product(space), 1)])
    return space, staff, request


def charge(space, request, subject_type, amount, status=Payment.Status.PENDING):
    return Payment.objects.create(makerspace=space, subject_type=subject_type, subject_id=request.pk,
                                  member=request.requester, amount=D(amount), currency="usd",
                                  created_by=request.requester, status=status)


def url(space, request, suffix=""):
    return f"/api/v1/admin/makerspace/{space.pk}/requests/{request.pk}/fee-waivers{suffix}"


def test_reason_required_and_return_authority_needed(loan):
    space, staff, request = loan
    assert client(staff).post(url(space, request), {"reason": "  "}, format="json").data["code"] == \
        "waiver_reason_required"
    events = staff_account(space, "waive-em", "event_manager")
    assert client(events).post(url(space, request), {"reason": "x"}, format="json").status_code == 404


def test_pending_fees_become_waived_paid_ones_open_a_case_and_the_deposit_stays(loan):
    space, staff, request = loan
    rental = charge(space, request, "loan_rental", "6.00")
    late = charge(space, request, "loan_late_fee", "4.00", status=Payment.Status.PAID_OFFLINE)
    deposit = charge(space, request, "loan_deposit", "10.00")
    response = client(staff).post(url(space, request), {"reason": "Broken on arrival"}, format="json")
    assert response.status_code == 201, response.data
    rental.refresh_from_db(), late.refresh_from_db(), deposit.refresh_from_db()
    assert rental.status == Payment.Status.WAIVED
    assert late.status == Payment.Status.PAID_OFFLINE  # never reversed automatically
    assert deposit.status == Payment.Status.PENDING
    case = RefundCase.objects.get(payment=late)
    assert (case.status, case.reason_code, case.due_amount) == ("open", "fee_waived", D("4.00"))
    assert response.data["refund_case_ids"] == [case.pk] and response.data["waived_payment_ids"] == [rental.pk]
    meta = AuditLog.objects.get(action="loan.fee_waived").meta
    assert meta["reason"] == "Broken on arrival" and meta["payment_ids"] == [rental.pk]


def test_future_charges_resolve_to_zero_and_revoke_restores_only_unraised(loan):
    space, staff, request = loan
    created = client(staff).post(url(space, request), {"components": ["rental"], "reason": "Goodwill"}, format="json")
    waiver_id = created.data["waiver"]["id"]
    priced = quote(space, "loans", request, params={"components": ("rental",), "days": 3})
    assert priced.total == 0 and priced.waiver["id"] == waiver_id and priced.lines[0].source == "waived"
    duplicate = client(staff).post(url(space, request), {"components": ["rental"], "reason": "x"}, format="json")
    assert duplicate.status_code == 409 and duplicate.data["code"] == "waiver_exists"
    revoked = client(staff).post(url(space, request, f"/{waiver_id}/revoke"), {"reason": "Mistake"}, format="json")
    assert revoked.status_code == 201, revoked.data
    assert quote(space, "loans", request, params={"components": ("rental",), "days": 3}).total == D("6.00")
    assert AuditLog.objects.filter(action="loan.fee_waiver_revoked").exists()


def test_waivers_are_append_only_in_the_model_and_the_database(loan):
    space, staff, request = loan
    waiver = LoanFeeWaiver.objects.create(makerspace=space, request=request, reason="r", created_by=staff)
    with pytest.raises(ValidationError):
        waiver.save()
    with pytest.raises(ValidationError):
        waiver.delete()
    with pytest.raises((IntegrityError, InternalError, Exception)):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("UPDATE payments_loanfeewaiver SET reason = 'x' WHERE id = %s", [waiver.pk])


def test_switch_off_hides_the_tool_but_written_waivers_still_apply(loan):
    space, staff, request = loan
    client(staff).post(url(space, request), {"reason": "Goodwill"}, format="json")
    switch(space, "loans.fee_waivers", on=False)
    assert client(staff).post(url(space, request), {"reason": "again"}, format="json").status_code == 404
    request.return_due_at = timezone.now() - timedelta(days=3)
    assert quote(space, "loans", request, params={"components": ("rental",), "days": 2}).total == 0
