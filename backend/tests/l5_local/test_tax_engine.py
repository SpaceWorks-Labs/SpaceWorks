"""G20: tax arithmetic, GSTIN checks, the frozen snapshot, and FY numbering (on and off)."""

from decimal import Decimal

import pytest

from apps.payments.models import MakerspaceTaxSettings, PaymentDocument
from apps.payments.tax import engine
from apps.payments.tax.apportion import apportion_figures, credit_note_split, figures_json
from apps.payments.tax.gstin import GstinError, validate_gstin
from apps.payments.tax.snapshot import freeze_for_charge
from tests.l5_local.helpers import dues, setup, switch

GSTIN_MH = "27AAPFU0939F1ZV"
GSTIN_KA = "29ABCDE1234F1ZW"
D = Decimal


def test_inclusive_and_exclusive_split_exactly():
    assert engine.tax_on(D("118.00"), 1800, inclusive=True, currency="inr") == (D("100.00"), D("18.00"), D("118.00"))
    assert engine.tax_on(D("100.00"), 1800, inclusive=False, currency="inr") == (D("100.00"), D("18.00"), D("118.00"))
    taxable, tax, gross = engine.tax_on(D("99.99"), 1800, inclusive=True, currency="inr")
    assert taxable + tax == gross == D("99.99")


def test_intra_state_halves_by_largest_remainder_and_inter_state_is_igst():
    cgst, sgst = engine.gst_components(D("0.03"), 1800, supply_type="intra", place_of_supply="27", currency="inr")
    assert (cgst.code, sgst.code) == ("cgst", "sgst") and cgst.amount + sgst.amount == D("0.03")
    (igst,) = engine.gst_components(D("18.00"), 1800, supply_type="inter", place_of_supply="29", currency="inr")
    assert igst.code == "igst" and igst.amount == D("18.00")
    (_, ut) = engine.gst_components(D("18.00"), 1800, supply_type="intra", place_of_supply="04", currency="inr")
    assert ut.code == "utgst"


@pytest.mark.parametrize("currency,quantum", [("jpy", D("1")), ("bhd", D("0.01")), ("inr", D("0.01"))])
def test_currency_exponents_cap_at_the_ledger_precision(currency, quantum):
    assert engine.quantum(currency) == quantum
    parts = engine.largest_remainder(D("10"), [1, 1, 1], currency)
    assert sum(parts) == D("10") and all(part % quantum == 0 for part in parts)


def test_partial_credit_notes_never_over_or_under_credit():
    invoice = figures_json(engine.compute(D("100.00"), {"mode": "gst_india", "supply_type": "intra",
                                                        "rate_bps": 1800, "place_of_supply": "27"}, "inr"))
    first = credit_note_split(invoice, [], D("33.33"), "inr")
    second = credit_note_split(invoice, [figures_json(first)], D("66.67"), "inr")
    assert first.taxable + second.taxable == D(invoice["taxable"])
    assert first.tax + second.tax == D(invoice["tax"])
    assert apportion_figures(invoice, D("100.00"), "inr").tax == D(invoice["tax"])


def test_gstin_check_character_state_and_format():
    assert validate_gstin(" 27aapfu0939f1zv ") == GSTIN_MH
    for bad in ("27AAPFU0939F1ZA", "99AAPFU0939F1ZV", "27AAPFU0939F1Z"):
        with pytest.raises(GstinError):
            validate_gstin(bad)


@pytest.mark.django_db
def test_tax_off_charges_exactly_release_one():
    space, _manager, payer = setup("tax-off")
    MakerspaceTaxSettings.objects.create(makerspace=space, mode="single", tax_name="VAT", rate_bps=2000,
                                         prices_include_tax=False)
    assert freeze_for_charge(space, D("50.00"), "eur", payer) == (D("50.00"), None)


@pytest.mark.django_db
def test_exclusive_single_tax_adds_on_top_and_freezes_the_figures():
    space, _manager, payer = setup("tax-single", "billing.tax")
    MakerspaceTaxSettings.objects.create(makerspace=space, mode="single", tax_name="VAT", rate_bps=2000,
                                         prices_include_tax=False)
    amount, snapshot = freeze_for_charge(space, D("50.00"), "eur", payer)
    assert amount == D("60.00") and snapshot["figures"]["tax"] == "10.00" and snapshot["tax_name"] == "VAT"


@pytest.mark.django_db
def test_gst_place_of_supply_and_lut_export():
    space, _manager, payer = setup("tax-gst", "billing.tax")
    MakerspaceTaxSettings.objects.create(makerspace=space, mode="gst_india", gstin=GSTIN_MH, state_code="27",
                                         foreign_currency="export_lut", lut_number="AD2704260001234")
    _amount, inr = freeze_for_charge(space, D("118.00"), "inr", payer)
    assert inr["supply_type"] == "intra" and {c["code"] for c in inr["figures"]["components"]} == {"cgst", "sgst"}
    _amount, usd = freeze_for_charge(space, D("100.00"), "usd", payer)
    assert usd["supply_type"] == "export_lut" and usd["figures"]["tax"] == "0.00"


@pytest.mark.django_db
def test_documents_take_the_fy_series_only_while_tax_is_on(django_capture_on_commit_callbacks):
    from apps.payments.reconciliation import mark_offline
    from tests.return_helpers import settlement_details

    space, manager, payer = setup("tax-fy")
    off = dues(space, payer, "10.00")
    mark_offline(off, manager, settlement_details(reference="CASH-1"))
    plain = PaymentDocument.objects.get(payment=off, kind="receipt")
    assert plain.number == "000001" and plain.fy_start is None and plain.tax_breakdown is None

    switch(space, "billing.tax")
    MakerspaceTaxSettings.objects.create(makerspace=space, mode="gst_india", gstin=GSTIN_MH, state_code="27")
    amount, snapshot = freeze_for_charge(space, D("118.00"), "inr", payer)
    taxed = dues(space, payer, str(amount), tax_snapshot=snapshot)
    mark_offline(taxed, manager, settlement_details(reference="CASH-2"))
    doc = PaymentDocument.objects.get(payment=taxed, kind="receipt")
    assert doc.number_series == "invoice" and doc.number.startswith("INV") and doc.number.endswith("/0001")
    assert len(doc.number) <= 16 and doc.tax_breakdown["title"] == "Tax invoice"
    assert doc.tax_breakdown["figures"]["tax"] == "18.00"
