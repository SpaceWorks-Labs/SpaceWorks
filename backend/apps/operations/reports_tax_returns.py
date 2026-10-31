"""GSTR-3B summary, monthly tax liability, the single-tax summary and the documents register.

* `gstr3b` -- per local month: 3.1(a) taxable outward supplies, 3.1(b) zero-rated
  (exports under LUT), 3.1(c) exempt, 3.1(e) non-GST, and 3.2 inter-state supplies to
  unregistered persons by place of supply; credit notes reduce the month they are issued in.
* `tax-summary` -- for the single-named-tax mode (VAT and the like): taxable value and
  tax per month, tax name and rate, net of credit notes.
* `documents-register` -- every receipt, tax invoice and credit note with its series, and
  a `gap` row wherever a per-FY series skips a number (Rule 46 requires gapless series).
"""

from collections import defaultdict
from decimal import Decimal

from apps.makerspaces.local_time import to_local
from apps.operations.report_types import ReportResult
from apps.operations.reports_finance_sources import finance_window, in_window

ZERO = Decimal("0.00")
B3_FIELDS = ("month", "section", "place_of_supply", "taxable", "igst", "cgst", "sgst")
SUMMARY_FIELDS = ("month", "tax_name", "rate", "currency", "taxable", "tax", "gross")
REGISTER_FIELDS = ("series", "financial_year", "number", "kind", "issued", "amount", "currency", "taxable", "tax",
                   "status")
SECTIONS = {"intra": "3.1a", "inter": "3.1a", "export_lut": "3.1b", "exempt": "3.1c", "composition": "3.1c",
            "no_gst": "3.1e"}


def _spaces(makerspace_id):
    from apps.operations.reports_bookkeeping_fy import _spaces as spaces
    return spaces(makerspace_id)


def _documents(space, date_range, **lookup):
    from apps.payments.models import PaymentDocument

    bounds = finance_window(space, date_range)
    rows = PaymentDocument.objects.filter(makerspace=space, **lookup).exclude(kind="bill").order_by("issued_at", "pk")
    return [doc for doc in rows if in_window(doc.issued_at, bounds)]


def build_gstr3b(makerspace_id, *, limit=None, date_range=None, actor=None):
    from apps.operations.reports_tax_gst import _components

    records = []
    for space in _spaces(makerspace_id):
        groups = defaultdict(lambda: {"taxable": ZERO, "igst": ZERO, "cgst": ZERO, "sgst": ZERO})
        for doc in _documents(space, date_range, tax_breakdown__mode="gst_india"):
            breakdown = doc.tax_breakdown
            sign = -1 if doc.kind == "credit_note" else 1
            month = to_local(space, doc.issued_at).strftime("%Y-%m")
            supply = breakdown.get("supply_type", "")
            taxable = Decimal(breakdown["figures"]["taxable"]) * sign
            parts = _components(breakdown, sign)
            keys = [(month, SECTIONS.get(supply, "3.1a"), "")]
            if supply == "inter" and not breakdown.get("recipient_gstin"):
                keys.append((month, "3.2", breakdown.get("place_of_supply", "")))
            for key in keys:
                groups[key]["taxable"] += taxable
                for name, value in parts.items():
                    groups[key][name] += value
        for (month, section, place), values in sorted(groups.items()):
            records.append({"month": month, "section": section, "place_of_supply": place, **values})
    return ReportResult(B3_FIELDS, records if limit is None else records[:limit], {
        "definition": "GSTR-3B outward supplies and liability by local month of the tax document.",
        "columns": "3.1a taxable, 3.1b zero-rated exports, 3.1c exempt or composition, 3.1e non-GST, 3.2 "
                   "inter-state supplies to unregistered persons by place of supply. sgst carries UTGST.",
    })


def build_tax_summary(makerspace_id, *, limit=None, date_range=None, actor=None):
    records = []
    for space in _spaces(makerspace_id):
        groups = defaultdict(lambda: {"taxable": ZERO, "tax": ZERO, "gross": ZERO})
        for doc in _documents(space, date_range, tax_breakdown__isnull=False):
            breakdown = doc.tax_breakdown
            figures = breakdown["figures"]
            sign = -1 if doc.kind == "credit_note" else 1
            key = (to_local(space, doc.issued_at).strftime("%Y-%m"), breakdown.get("tax_name") or "GST",
                   Decimal(breakdown.get("rate_bps", 0)) / 100, doc.currency)
            for name in ("taxable", "tax", "gross"):
                groups[key][name] += Decimal(figures[name]) * sign
        for (month, name, rate, currency), values in sorted(groups.items()):
            records.append({"month": month, "tax_name": name, "rate": rate, "currency": currency, **values})
    return ReportResult(SUMMARY_FIELDS, records if limit is None else records[:limit], {
        "definition": "Tax charged per local month, tax name, rate and currency, net of credit notes.",
    })


def build_documents_register(makerspace_id, *, limit=None, date_range=None, actor=None):
    from apps.payments.tax.document_tax import taxable_and_tax
    from apps.payments.tax.fy import fy_name

    records = []
    for space in _spaces(makerspace_id):
        documents = _documents(space, date_range)
        series = defaultdict(set)
        for doc in documents:
            taxable, tax = taxable_and_tax(doc)
            label = doc.number_series or "receipts"
            year = fy_name(doc.fy_start) if doc.fy_start else ""
            records.append({"series": label, "financial_year": year, "number": doc.number, "kind": doc.kind,
                            "issued": to_local(space, doc.issued_at).date(), "amount": doc.amount,
                            "currency": doc.currency, "taxable": taxable, "tax": tax, "status": "issued"})
            if doc.fy_start:
                series[(label, doc.fy_start)].add(doc.sequence)
        records.extend(_gaps(space, series))
    return ReportResult(REGISTER_FIELDS, records if limit is None else records[:limit], {
        "definition": "Every receipt, tax invoice and credit note issued in the window, with a gap row for "
                      "each number a per-financial-year series skipped.",
        "columns": "status=issued, or gap for a missing number between the first and last issued.",
    })


def _gaps(space, series):
    from apps.payments.models import PaymentDocument
    from apps.payments.tax.fy import fy_name

    rows = []
    for (label, start), seen in sorted(series.items(), key=lambda item: (item[0][0], item[0][1])):
        issued = set(PaymentDocument.objects.filter(makerspace=space, number_series=label, fy_start=start)
                     .values_list("sequence", flat=True))
        for missing in sorted(set(range(1, max(issued | seen) + 1)) - issued):
            rows.append({"series": label, "financial_year": fy_name(start), "number": str(missing), "kind": "",
                         "issued": None, "amount": None, "currency": "", "taxable": None, "tax": None,
                         "status": "gap"})
    return rows
