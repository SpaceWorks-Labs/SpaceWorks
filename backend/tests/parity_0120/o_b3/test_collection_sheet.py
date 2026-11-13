"""O-B3: the collection sheet goes through the offline settlement service and keeps maker-checker."""
import pytest

from apps.payments.models import ManualSettlement, Payment, SettlementConfirmation
from tests.l5_local.helpers import client, dues, setup, staff

pytestmark = pytest.mark.django_db


def _url(space):
    return f"/api/v1/admin/makerspace/{space.pk}/billing/collection-sheet"


def _rows(*payments, method="cash"):
    return {"rows": [{"payment_id": payment.pk, "method": method, "reference": f"R{payment.pk}"}
                     for payment in payments]}


def test_off_by_default_404s():
    space, manager, payer = setup("sheet-off")
    assert client(manager).post(_url(space), _rows(dues(space, payer)), format="json").status_code == 404


def test_each_row_is_one_settlement_and_a_bad_row_fails_alone():
    space, manager, payer = setup("sheet-on", "billing.collection_sheet")
    first, second = dues(space, payer), dues(space, payer, "5.00")
    paid = dues(space, payer, "7.00")
    Payment.objects.filter(pk=paid.pk).update(status=Payment.Status.WAIVED)
    body = _rows(first, second, paid, first)
    body["rows"].append({"payment_id": 999999, "method": "cash"})
    data = client(manager).post(_url(space), body, format="json").json()
    outcomes = [row["outcome"] for row in data["results"]]
    assert outcomes == ["recorded", "recorded", "failed", "failed", "failed"]
    assert data["results"][2]["code"] == "payment_terminal" and data["results"][3]["code"] == "duplicate_in_sheet"
    assert data["summary"] == {"rows": 5, "recorded": 2, "awaiting_confirmation": 0, "failed": 3}
    assert ManualSettlement.objects.filter(payment__in=[first, second]).count() == 2


def test_maker_checker_still_needs_a_second_person():
    space, manager, payer = setup("sheet-checker", "billing.collection_sheet", "billing.maker_checker")
    payment = dues(space, payer)
    data = client(manager).post(_url(space), _rows(payment), format="json").json()
    assert data["results"][0]["outcome"] == "awaiting_confirmation" and not ManualSettlement.objects.exists()
    row = SettlementConfirmation.objects.get()
    own = client(manager).post(f"/api/v1/admin/makerspace/{space.pk}/settlements/{row.pk}/confirm")
    assert own.status_code == 409 and own.json()["code"] == "self_confirmation"
    second = staff("sheet-checker", space, "space_manager")
    assert client(second).post(f"/api/v1/admin/makerspace/{space.pk}/settlements/{row.pk}/confirm").status_code == 200


def test_more_than_200_rows_is_a_400_and_the_monthly_allowance_is_a_typed_409():
    space, manager, payer = setup("sheet-limits", "billing.collection_sheet")
    too_many = {"rows": [{"payment_id": 1, "method": "cash"}] * 201}
    assert client(manager).post(_url(space), too_many, format="json").status_code == 400
    space.resource_limit_overrides = {"collection_sheet_rows_monthly": 1}
    space.save(update_fields=["resource_limit_overrides"])
    two = _rows(dues(space, payer), dues(space, payer, "5.00"))
    refused = client(manager).post(_url(space), two, format="json")
    assert refused.status_code == 409 and refused.json()["code"] == "collection_sheet_rows_monthly_quota_reached"
    assert not ManualSettlement.objects.exists()


def test_another_space_cannot_use_the_sheet():
    space, _manager, payer = setup("sheet-a", "billing.collection_sheet")
    _other, other_manager, _ = setup("sheet-b", "billing.collection_sheet")
    assert client(other_manager).post(_url(space), _rows(dues(space, payer)), format="json").status_code == 404
