"""GSTR-1 tables from issued tax documents (G22). Read-only; documents are the source of truth.

Every figure comes from a document's frozen `tax_breakdown`, never from today's settings,
so a return for a closed month reads the same forever. Tables:

* B2B (4A) -- tax invoices to a recipient with a GSTIN, one row per invoice;
* B2CL (5) -- inter-state invoices to unregistered recipients above the B2CL limit;
* B2CS (7) -- every other unregistered supply, summed by place of supply and rate, net of
  credit notes to unregistered recipients;
* EXP (6A) -- exports under LUT; CDNR (9B) -- credit notes to registered recipients;
* NIL (8) -- exempt and non-GST supplies; HSN (12) -- by SAC code; DOCS (13) -- series.
"""

from collections import defaultdict
from decimal import Decimal

from apps.makerspaces.local_time import to_local

B2CL_LIMIT = Decimal("100000")  # Notification 12/2024-CT: inter-state B2C invoices above Rs 1 lakh.
ZERO = Decimal("0.00")
TABLE_FIELDS = ("table", "document", "date", "recipient_gstin", "place_of_supply", "rate", "taxable", "igst",
                "cgst", "sgst", "value")


def gst_documents(space, bounds):
    """GST-mode documents issued in [start, end) with a frozen breakdown, oldest first."""
    from apps.operations.reports_finance_sources import in_window
    from apps.payments.models import PaymentDocument

    rows = PaymentDocument.objects.filter(makerspace=space, tax_breakdown__mode="gst_india").exclude(
        kind="bill").order_by("issued_at", "pk")
    return [doc for doc in rows if in_window(doc.issued_at, bounds)]


def _components(breakdown, sign=1):
    totals = {"igst": ZERO, "cgst": ZERO, "sgst": ZERO}
    for item in breakdown["figures"].get("components", []):
        code = "sgst" if item["code"] in ("sgst", "utgst") else item["code"]
        if code in totals:
            totals[code] += Decimal(item["amount"]) * sign
    return totals


def _row(space, table, doc, sign=1):
    breakdown = doc.tax_breakdown
    figures = breakdown["figures"]
    return {"table": table, "document": doc.number, "date": to_local(space, doc.issued_at).date(),
            "recipient_gstin": breakdown.get("recipient_gstin", ""), "place_of_supply": breakdown.get(
                "place_of_supply", ""), "rate": Decimal(breakdown.get("rate_bps", 0)) / 100,
            "taxable": Decimal(figures["taxable"]) * sign, **_components(breakdown, sign),
            "value": Decimal(figures["gross"]) * sign}


def gstr1_tables(space, bounds):
    tables = defaultdict(list)
    b2cs = defaultdict(lambda: {"taxable": ZERO, "igst": ZERO, "cgst": ZERO, "sgst": ZERO, "value": ZERO})
    nil = defaultdict(lambda: ZERO)
    hsn = defaultdict(lambda: {"count": 0, "taxable": ZERO, "igst": ZERO, "cgst": ZERO, "sgst": ZERO, "value": ZERO})
    documents = gst_documents(space, bounds)
    for doc in documents:
        breakdown = doc.tax_breakdown
        supply = breakdown.get("supply_type")
        credit = doc.kind == "credit_note"
        sign = -1 if credit else 1
        registered = bool(breakdown.get("recipient_gstin"))
        row = _row(space, "", doc, sign)
        if supply in ("exempt", "no_gst", "composition"):
            nil[(supply, "inter" if breakdown.get("place_of_supply") != breakdown.get("supplier_state") else "intra")] \
                += row["value"]
            continue
        if supply == "export_lut":
            tables["exp"].append({**row, "table": "exp"})
        elif credit and registered:
            tables["cdnr"].append({**row, "table": "cdnr"})
        elif registered:
            tables["b2b"].append({**row, "table": "b2b"})
        elif supply == "inter" and not credit and Decimal(breakdown["figures"]["gross"]) > B2CL_LIMIT:
            tables["b2cl"].append({**row, "table": "b2cl"})
        else:
            group = b2cs[(row["place_of_supply"], row["rate"])]
            for key in group:
                group[key] += row[key]
        sac = hsn[(breakdown.get("sac_code", ""), row["rate"])]
        sac["count"] += sign
        for key in ("taxable", "igst", "cgst", "sgst", "value"):
            sac[key] += row[key]
    for (place, rate), values in sorted(b2cs.items()):
        tables["b2cs"].append({"table": "b2cs", "document": "", "date": None, "recipient_gstin": "",
                               "place_of_supply": place, "rate": rate, **values})
    for (supply, scope), value in sorted(nil.items()):
        tables["nil"].append({"table": "nil", "document": supply, "date": None, "recipient_gstin": "",
                              "place_of_supply": scope, "rate": ZERO, "taxable": value, "igst": ZERO,
                              "cgst": ZERO, "sgst": ZERO, "value": value})
    for (sac, rate), values in sorted(hsn.items()):
        tables["hsn"].append({"table": "hsn", "document": sac, "date": None, "recipient_gstin": "",
                              "place_of_supply": str(values.pop("count")), "rate": rate, **values})
    tables["docs"] = document_series(documents)
    return tables


def document_series(documents):
    """Table 13: per series, the first and last number and how many were issued."""
    series = defaultdict(list)
    for doc in documents:
        series[(doc.number_series, doc.fy_start)].append(doc)
    rows = []
    for (name, _start), docs in sorted(series.items(), key=lambda item: (item[0][0], str(item[0][1]))):
        docs.sort(key=lambda doc: doc.sequence)
        rows.append({"table": "docs", "document": name, "date": None, "recipient_gstin": "",
                     "place_of_supply": f"{docs[0].number} - {docs[-1].number}", "rate": ZERO,
                     "taxable": Decimal(len(docs)), "igst": ZERO, "cgst": ZERO, "sgst": ZERO, "value": ZERO})
    return rows


def build_gstr1(makerspace_id, *, limit=None, date_range=None, actor=None):
    from apps.operations.report_types import ReportResult
    from apps.operations.reports_finance_sources import finance_window
    from apps.operations.reports_bookkeeping_fy import _spaces

    records = []
    for space in _spaces(makerspace_id):
        tables = gstr1_tables(space, finance_window(space, date_range))
        for name in ("b2b", "b2cl", "b2cs", "exp", "cdnr", "nil", "hsn", "docs"):
            records.extend(tables.get(name, []))
    return ReportResult(TABLE_FIELDS, records if limit is None else records[:limit], {
        "definition": "GSTR-1 rows from tax documents issued in the window (local issue date). Credit notes "
                      "carry negative amounts. Choose one calendar month to file.",
        "columns": "table=b2b|b2cl|b2cs|exp|cdnr|nil|hsn|docs; sgst also carries UTGST; for hsn rows "
                   "place_of_supply holds the document count, for docs rows the number range and taxable the "
                   "number of documents.",
    })
