"""L22 ledger: domain tagging, #100 visibility, report rows, the payments touchpoints, tax classes."""

from decimal import Decimal

import pytest

from apps.payments.models import Payment

from .helpers import client, line, manager, payment_for, product, shop_manager, shop_space

pytestmark = pytest.mark.django_db


def _sale(space, seller, variant, qty=1):
    response = client(seller).post(f"/api/v1/admin/makerspaces/{space.pk}/shop/pos/sale/",
                                   {"lines": [line(variant, qty)], "method": "cash"}, format="json")
    assert response.status_code == 201, response.content
    from apps.shop.models import ShopOrder
    return ShopOrder.objects.get(pk=response.json()["id"])


def test_every_touchpoint_knows_the_shop_subject():
    from apps.payments.availability import SUBJECT_DOMAINS
    from apps.payments.finance_scope import DOMAIN_ACTIONS, PAYMENT_DOMAINS
    from apps.payments.models import RefundCase
    from apps.payments.pricing.components import DOMAINS, component
    from apps.payments.reconciliation_authority import CASH_RECORD_ACTIONS, SUBJECT_ACTIONS
    from apps.tenant_migration.references import PAYMENT_SUBJECT_REFERENCES

    assert Payment.SubjectType.SHOP_ORDER == "shop_order"
    assert SUBJECT_DOMAINS["shop_order"] == PAYMENT_DOMAINS["shop_order"] == "shop"
    assert DOMAIN_ACTIONS["shop"] == "manage_shop"
    assert SUBJECT_ACTIONS["shop_order"] == CASH_RECORD_ACTIONS["shop_order"] == "manage_shop"
    assert "shop" in RefundCase.Area.values and "shop_return" in RefundCase.ReasonCode.values
    assert PAYMENT_SUBJECT_REFERENCES["shop_order"] == "shop.ShopOrder"
    assert component("shop", "item").subject_type == "shop_order" and "shop" in DOMAINS
    assert "shop_order" in Payment.ACCOUNTLESS_SUBJECT_TYPES


def test_a_sale_is_income_in_the_shop_domain_of_the_ledger():
    from apps.payments.finance_rows import money_rows

    space = shop_space("led-a")
    seller = shop_manager(space)
    _row, variant = product(space, seller, price="120.00")
    order = _sale(space, seller, variant)
    rows = [row for row in money_rows(space) if row.subject_type == "shop_order"]
    assert rows and {row.domain for row in rows} == {"shop"} and sum(row.amount for row in rows) == Decimal("120.00")
    assert payment_for(order).subject_label.startswith("Shop order")


def test_the_shop_reports_need_only_manage_shop():
    from apps.operations.report_registry import REPORT_REGISTRY
    from apps.operations.reports_shop import build_shop_sales
    from apps.payments.reports_finance_ledger import build_finance_shop

    assert REPORT_REGISTRY["shop-sales"].required_action == "manage_shop"
    assert REPORT_REGISTRY["finance-shop"].required_action == "manage_shop"
    space = shop_space("led-b", "finance.ledger")
    seller = shop_manager(space)
    _row, variant = product(space, seller, price="30.00")
    _sale(space, seller, variant, qty=2)
    sales = build_shop_sales(space.pk).records
    assert sales[0]["channel"] == "pos" and sales[0]["sales"] == Decimal("60.00") and sales[0]["units"] == 2
    ledger = build_finance_shop(space.pk, actor=seller).records
    assert ledger and {row["domain"] for row in ledger} == {"shop"}
    summary = client(seller).get(f"/api/v1/admin/makerspaces/{space.pk}/shop/report/").json()
    assert summary["totals"]["orders"] == 1 and Decimal(summary["totals"]["sales"]) == Decimal("60.00")
    assert summary["by_method"] == [{"method": "cash", "amount": "60.00"}]


def test_tax_classes_freeze_one_snapshot_from_the_lines():
    from apps.payments.tax.models_tax import MakerspaceTaxSettings

    space = shop_space("led-c", "billing.tax", "shop.tax", "shop.receipts")
    # GST applies to an INR invoice; a foreign-currency one is "outside GST" by default (tax settings foreign_currency).
    from apps.payments.models import MakerspacePaymentSettings
    MakerspacePaymentSettings.objects.update_or_create(makerspace=space, defaults={"default_currency": "inr"})
    MakerspaceTaxSettings.objects.create(makerspace=space, mode="gst_india", gstin="29ABCDE1234F1ZW", state_code="29",
                                         rate_bps=1800, prices_include_tax=True)
    seller = shop_manager(space)
    _a, food = product(space, seller, name="Snack", price="105.00", tax_rate_bps=500, hsn_code="1905")
    _b, tool = product(space, seller, name="Pliers", price="118.00")
    response = client(seller).post(f"/api/v1/admin/makerspaces/{space.pk}/shop/pos/sale/",
                                   {"lines": [line(food), line(tool)], "method": "cash"}, format="json")
    assert response.status_code == 201, response.content
    from apps.shop.models import ShopOrder
    order = ShopOrder.objects.get(pk=response.json()["id"])
    payment = payment_for(order)
    figures = payment.tax_snapshot["figures"]
    assert payment.amount == Decimal("223.00") and Decimal(figures["gross"]) == Decimal("223.00")
    assert Decimal(figures["tax"]) == Decimal("5.00") + Decimal("18.00")
    assert Decimal(figures["taxable"]) + Decimal(figures["tax"]) == Decimal("223.00")
    snack = order.lines.get(hsn_code="1905")
    assert (snack.tax_rate_bps, snack.tax_amount) == (500, Decimal("5.00"))
    receipt = client(seller).get(f"/api/v1/admin/shop/orders/{order.pk}/receipt/").json()
    assert {row["hsn_code"] for row in receipt["lines"]} == {"1905", ""}


def test_with_charge_tracking_off_the_shop_refuses_to_sell():
    from .helpers import switch

    space = shop_space("led-d")
    seller = shop_manager(space)
    _row, variant = product(space, seller)
    switch(space, "charges.shop", on=False)
    response = client(seller).post(f"/api/v1/admin/makerspaces/{space.pk}/shop/pos/sale/",
                                   {"lines": [line(variant)], "method": "cash"}, format="json")
    assert response.status_code == 409 and response.json()["code"] == "charges_off"


def test_a_free_item_raises_no_charge():
    space = shop_space("led-e")
    seller = manager(space)
    _row, variant = product(space, seller, price="0.00")
    order = _sale(space, seller, variant)
    assert payment_for(order) is None and order.status == "collected"
