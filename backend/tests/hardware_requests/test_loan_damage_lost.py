"""Lane L15 (A5): staff-set damage/lost charges, one per row, return photo required."""

from decimal import Decimal

import pytest

from apps.audit.models import AuditLog
from apps.hardware_requests import workflow
from apps.hardware_requests.models import RequesterAccountability
from apps.payments.models import Payment
from tests.hardware_requests.test_loan_payments import quiet_storage_and_stripe  # noqa: F401
from tests.fixed_roles.helpers import staff_account
from tests.payments.pricing.helpers import D, client, pricing_space, rate
from tests.return_helpers import make_issued_request, make_product, make_return_evidence

pytestmark = pytest.mark.django_db


def damaged_return(space, staff, product, *, damaged=1, missing=0, callbacks=None):
    request = make_issued_request(space, staff, [(product, damaged + missing)])
    evidence = make_return_evidence(space, staff)
    item = request.items.get()
    with callbacks(execute=True):
        workflow.return_items(staff, request, evidence.pk, "Checked.", request.assigned_box.code,
                              [{"item_id": item.pk, "returned": 0, "damaged": damaged, "missing": missing}])
    return request


def url(space, request, row):
    return f"/api/v1/admin/makerspace/{space.pk}/requests/{request.pk}/accountability/{row.pk}/charge"


@pytest.fixture
def setup():
    space, _ = pricing_space("dmg")
    staff = staff_account(space, "dmg-staff", "space_manager")
    return space, staff


def test_damage_charge_is_raised_once_with_the_return_photo(setup, django_capture_on_commit_callbacks):
    space, staff = setup
    rate(space, "loans", damage="12.00")
    product = make_product(space, unit_cost=Decimal("40"))
    request = damaged_return(space, staff, product, callbacks=django_capture_on_commit_callbacks)
    row = RequesterAccountability.objects.get(request=request)
    charges = client(staff).get(f"/api/v1/admin/makerspace/{space.pk}/requests/{request.pk}/charges")
    assert charges.status_code == 200, charges.data
    listed = charges.data["accountability"][0]
    assert (listed["suggested_amount"], listed["has_return_photo"]) == ("12.00", True)
    response = client(staff).post(url(space, request, row), {"amount": "15.00", "note": "Cracked lens"}, format="json")
    assert response.status_code == 200, response.data
    payment = Payment.objects.get(subject_type="loan_damage", subject_id=row.pk)
    assert payment.amount == D("15.00") and payment.member_id == request.requester_id
    assert payment.pricing_snapshot["lines"][0]["detail"]["evidence_id"] == row.evidence_photo_id
    meta = AuditLog.objects.get(action="loan.damage_charged").meta
    assert meta["accountability_id"] == row.pk and meta["note"] == "Cracked lens"
    again = client(staff).post(url(space, request, row), {"amount": "1.00"}, format="json")
    assert again.status_code == 409 and again.data["code"] == "charge_exists"


def test_lost_suggestion_falls_back_to_unit_cost(setup, django_capture_on_commit_callbacks):
    space, staff = setup
    product = make_product(space, unit_cost=Decimal("25.5"))
    request = damaged_return(space, staff, product, damaged=0, missing=2, callbacks=django_capture_on_commit_callbacks)
    from apps.hardware_requests.loan_payments import suggestion
    row = RequesterAccountability.objects.get(request=request)
    assert suggestion(row) == (D("51.00"), "unit_cost")
    assert client(staff).post(url(space, request, row), {"amount": "51.00"}, format="json").status_code == 200
    assert Payment.objects.get(subject_type="loan_lost", subject_id=row.pk).amount == D("51.00")


def test_a_row_without_its_return_photo_cannot_be_charged(setup, django_capture_on_commit_callbacks):
    space, staff = setup
    product = make_product(space)
    request = make_issued_request(space, staff, [(product, 1)])
    row = RequesterAccountability.objects.create(requester=request.requester, request=request,
                                                 request_item=request.items.get(), makerspace=space,
                                                 issue_type="damaged", quantity=1, created_by=staff)
    refused = client(staff).post(url(space, request, row), {"amount": "5.00"}, format="json")
    assert refused.status_code == 409 and refused.data["code"] == "return_photo_required"
    nothing = client(staff).post(url(space, request, row), {"amount": "0"}, format="json")
    assert nothing.status_code == 200 and nothing.data["charge"] is None
    assert AuditLog.objects.filter(action="loan.accountability_not_charged", meta__accountability_id=row.pk).exists()
    listed = client(staff).get(f"/api/v1/admin/makerspace/{space.pk}/requests/{request.pk}/charges")
    assert listed.data["accountability"][0]["no_charge_decided"] is True
    assert not Payment.objects.filter(subject_type="loan_damage").exists()


def test_only_return_authority_may_charge(setup, django_capture_on_commit_callbacks):
    space, staff = setup
    request = damaged_return(space, staff, make_product(space), callbacks=django_capture_on_commit_callbacks)
    row = RequesterAccountability.objects.get(request=request)
    events = staff_account(space, "dmg-em", "event_manager")
    assert client(events).post(url(space, request, row), {"amount": "5.00"}, format="json").status_code == 404
    handover = staff_account(space, "dmg-im", "inventory_manager")
    assert client(handover).post(url(space, request, row), {"amount": "5.00"}, format="json").status_code == 200
