"""The core ledger remains readable/settleable after each money/domain switch is off."""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.payments.models import ManualSettlement, Payment
from tests.payments.ledger_fixtures_cx11b_g5 import receipt, seed, settled
from tests.payments.route_support_cx11b_g5 import cycle, hidden, ids, world

pytestmark = [pytest.mark.django_db, pytest.mark.area_payments_ledger]
OPS = ("list", "mark-offline", "waive", "bulk-mark-offline", "bulk-waive", "amend-settlement")


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["payments", "charges.enabled", "membership", "charges.membership"])
@pytest.mark.parametrize("operation", OPS)
def test_reconciliation_route_exact_effect_standing_and_core_switch_independence(native, key, operation):
    s = seed(native)
    amend, listing, bulk = operation == "amend-settlement", operation == "list", operation.startswith("bulk-")
    if amend:
        settled(s)
    kwargs = {"makerspace_id": s.space.pk}
    if not listing and not bulk:
        kwargs["payment_id"] = s.payment.pk
    body = {"ids": [s.payment.pk]} if bulk else {}
    if "offline" in operation or amend:
        value = receipt()
        value["received_at"] = value["received_at"].isoformat()
        body["settlement"] = value
    name = "payment-settlement-amend" if amend else "payment-reconciliation-" + operation
    action = "payment.settlement_amended" if amend else "payment.paid_offline" if "offline" in operation else "payment.waived"

    def result(response):
        saved = Payment.objects.get(pk=s.payment.pk)
        assert (saved.amount, saved.currency, saved.provider) == (Decimal("100"), "inr", "unclaimed")
        if listing:
            assert ids(response) == [saved.pk]
            assert Decimal(response.data["results"][0]["amount"]) == Decimal("100")
            assert saved.status == "pending" and saved.manual_settlements.count() == 0
        else:
            row = response.data[0] if bulk else response.data
            expected = "paid_offline" if "offline" in operation or amend else "waived"
            assert saved.status == row["status"] == expected
            if expected == "paid_offline":
                effective = ManualSettlement.effective_for(saved)
                assert (effective.method, effective.reference, effective.amount, effective.currency) == (
                    "cash", "G5-RECEIPT", Decimal("100"), "inr")
                assert saved.manual_settlements.count() == (2 if amend else 1)
                if amend:
                    assert effective.amends.reference == "G5-SEED"
                    assert effective.amends.amount == effective.amount
            else:
                assert saved.manual_settlements.count() == 0
    # 481/494: these staff routes carry makerspace_id, so an outsider sees uniform not_found.
    w = world(s.space, s.client, reverse(name, kwargs=kwargs), "GET" if listing else "POST", body,
              audit=() if listing else (action,), check=result, probes=[hidden(s.foreign)])
    cycle(w, key)
