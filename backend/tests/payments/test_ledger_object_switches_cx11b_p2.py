"""Seeded ledger surfaces remain usable without the optional online rail."""
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.payments.models import MakerspaceBillingSettings, MakerspacePaymentSettings, PaymentDispute, PriceDiscount
from apps.payments.ledger_api import record_expense
from apps.payments.offline_claims import submit_claim
from tests.accounts.account_factories import make_staff
from tests.l5_local.helpers import accountless, dues
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.modules.switch_matrix_object_helpers import client_for
from tests.payments.account_helpers import make_payer
from tests.payments.switch_helpers_cx11b_p2 import route_cycle, switch

pytestmark = [pytest.mark.django_db, pytest.mark.area_payments_ledger]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["billing.disputes", "billing.offline_claims", "billing.pay_links",
    "billing.collection_sheet", "finance.ledger", "charges.discounts", "charges.pricing"])
def test_seeded_ledger_switch_refuses_without_writes_and_restores_object_with_rail_absent(native, key):
    space = live_space("p2-ledger-object", set(MODULE_KEYS) - {"payments"})
    seller = make_staff(space, username="p2-ledger-manager", access_status="active")
    payer = make_payer("p2-ledger-payer", space)
    client = client_for(seller, space, native)
    policy, _ = MakerspaceBillingSettings.objects.get_or_create(makerspace=space)
    MakerspacePaymentSettings.objects.get_or_create(makerspace=space)
    payment = dues(space, payer, provider="unclaimed")
    objects, kwargs = {"debt": payment, "billing": policy}, {"makerspace_id": space.pk}
    method, body, on, off = "get", None, (200, None), (404, "feature_disabled")
    if key == "billing.disputes":
        row = PaymentDispute.objects.create(makerspace=space, payment=payment, provider="stripe",
            provider_dispute_id="dp_p2_test", amount=payment.amount, currency=payment.currency)
        objects["dispute"], name, kwargs["dispute_id"] = row, "dispute-detail", row.pk
    elif key == "billing.offline_claims":
        row = submit_claim(payment, claimant=payer, reference="P2-CLAIM", paid_on=timezone.localdate())
        objects["claim"], name = row, "paid-claim-list"
    elif key == "billing.pay_links":
        extra = accountless(space, seller)
        objects["accountless_debt"] = extra
        name, kwargs["payment_id"], method, body, on = "payment-pay-link", extra.pk, "post", {}, (201, None)
    elif key == "billing.collection_sheet":
        # Keep one transaction per row, paid offline with a real immutable receipt.
        switch(space, "billing.maker_checker")
        name, method, on = "billing-collection-sheet", "post", (200, None)
        body = {"rows": [{"payment_id": payment.pk, "method": "cash", "reference": "P2-CASH"}]}
    elif key == "finance.ledger":
        row = record_expense(space, "general", None, Decimal("4.50"), "inr", "cash", "P2-EXPENSE",
            None, "switch_p2", "one", seller)
        objects["expense"], name, kwargs["entry_id"] = row, "finance-entry", row.pk
    else:
        row = PriceDiscount.objects.create(makerspace=space, name="Retained discount", audience="all_members",
            percent_bps=1000, domains=["loans"], created_by=seller)
        objects["discount"], name, kwargs["discount_id"] = row, "pricing-discount", row.pk
        method, body = "patch", {"name": "Updated discount"}
        off = (404, "pricing_disabled")
    response = route_cycle(space, client, objects, key, reverse(name, kwargs=kwargs),
        method=method, body=body, on=on, off=off)
    if key in {"charges.discounts", "charges.pricing"}:
        row.refresh_from_db()
        assert row.name == response.data["name"] == "Updated discount"
    if key == "billing.collection_sheet":
        assert response.data["summary"] == {"rows": 1, "recorded": 1, "awaiting_confirmation": 0, "failed": 0}
        payment.refresh_from_db()
        assert (payment.status, payment.provider) == ("paid_offline", "unclaimed")
        assert payment.manual_settlements.get().reference == "P2-CASH"
