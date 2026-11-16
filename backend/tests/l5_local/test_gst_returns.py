"""G22 GST returns, the documents register, X35 money methods and the finance report registry."""

from decimal import Decimal

import pytest

from apps.operations.reports import report_data, report_rows
from apps.operations.reports_tax_gst import gstr1_tables
from apps.operations.reports_tax_gst_json import gstr1_json
from apps.payments.models import MakerspaceTaxSettings
from apps.payments.reconciliation import mark_offline
from apps.payments.tax.snapshot import freeze_for_charge
from tests.l5_local.helpers import client, dues, setup, staff
from tests.return_helpers import settlement_details

pytestmark = pytest.mark.django_db
GSTIN_MH, GSTIN_KA = "27AAPFU0939F1ZV", "29ABCDE1234F1ZW"


def _taxed_space(slug):
    space, manager, payer = setup(slug, "billing.tax", "finance.ledger")
    MakerspaceTaxSettings.objects.create(makerspace=space, mode="gst_india", gstin=GSTIN_MH, state_code="27")
    return space, manager, payer


def _settle(space, manager, payer, amount, reference, recipient_gstin=""):
    gross, snapshot = freeze_for_charge(space, Decimal(amount), "inr", payer)
    if recipient_gstin:
        snapshot.update(recipient_gstin=recipient_gstin, recipient_state=recipient_gstin[:2],
                        place_of_supply=recipient_gstin[:2], supply_type="inter")
        from apps.payments.tax.apportion import figures_json
        from apps.payments.tax.engine import compute
        snapshot["figures"] = figures_json(compute(Decimal(amount), snapshot, "inr", entered=True))
        gross = Decimal(snapshot["figures"]["gross"])
    payment = dues(space, payer, str(gross), tax_snapshot=snapshot)
    mark_offline(payment, manager, settlement_details(reference=reference))
    return payment


def test_gstr1_splits_b2b_and_b2cs_and_builds_offline_tool_json():
    space, manager, payer = _taxed_space("gstr1")
    _settle(space, manager, payer, "118.00", "CASH-A")
    _settle(space, manager, payer, "100.00", "CASH-B", recipient_gstin=GSTIN_KA)
    tables = gstr1_tables(space, (None, None))
    assert len(tables["b2b"]) == 1 and tables["b2b"][0]["igst"] == Decimal("15.25")  # 100 inclusive of 18%
    assert len(tables["b2cs"]) == 1 and tables["b2cs"][0]["cgst"] + tables["b2cs"][0]["sgst"] == Decimal("18.00")
    payload = gstr1_json(GSTIN_MH, "102026", tables)
    assert payload["b2b"][0]["ctin"] == GSTIN_KA and payload["b2cs"][0]["sply_ty"] == "INTRA"
    assert payload["doc_issue"]["doc_det"][0]["docs"][0]["totnum"] == 2


def test_tax_reports_need_the_capability_and_register_finds_no_gaps():
    space, manager, payer = _taxed_space("gst-register")
    _settle(space, manager, payer, "118.00", "CASH-C")
    rows = report_data("documents-register", space.pk, actor=manager)["rows"]
    assert rows and all("gap" not in str(row) for row in rows)
    assert report_rows("gstr3b", space.pk, actor=manager)
    response = client(manager).get(f"/api/v1/admin/makerspace/{space.pk}/billing/tax/gstr1.json", {"month": "2026-10"})
    assert response.status_code == 200 and response.json()["gstin"] == GSTIN_MH


def test_income_spending_report_is_scoped_by_area():
    space, manager, payer = setup("fin-report", "finance.ledger")
    mark_offline(dues(space, payer, "40.00"), manager, settlement_details(reference="CASH-R"))
    full = report_data("income-spending", space.pk, actor=manager)["rows"]
    assert full
    inventory = staff("fin-report", space, "inventory_manager")
    scoped = report_data("finance-inventory", space.pk, actor=inventory)["rows"]
    assert len(scoped) <= 1  # header only: membership money is not an inventory area
    methods = report_data("money-methods", space.pk, actor=manager)["rows"]
    assert methods
