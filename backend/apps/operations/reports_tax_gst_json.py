"""GSTR-1 in the GSTN offline-tool JSON shape, built from `reports_tax_gst.gstr1_tables`.

Amounts are rupees with two decimals, dates dd-mm-yyyy, the return period MMYYYY. Credit
notes are reported as positive note values (`ntty` C). The file is a draft for the
offline tool: staff review it there before filing, nothing is sent to the GSTN.
"""

from decimal import Decimal


def _amount(value):
    return float(abs(Decimal(value)).quantize(Decimal("0.01")))


def _date(value):
    return value.strftime("%d-%m-%Y") if value else ""


def _items(row):
    return [{"num": 1, "itm_det": {"txval": _amount(row["taxable"]), "rt": float(row["rate"]),
                                   "iamt": _amount(row["igst"]), "camt": _amount(row["cgst"]),
                                   "samt": _amount(row["sgst"]), "csamt": 0}}]


def _invoice(row):
    return {"inum": row["document"], "idt": _date(row["date"]), "val": _amount(row["value"]),
            "pos": row["place_of_supply"], "rchrg": "N", "inv_typ": "R", "itms": _items(row)}


def _doc_issue(rows):
    """Table 13: invoices are document type 1, credit notes type 5."""
    grouped = {}
    for row in rows:
        first, _, last = row["place_of_supply"].partition(" - ")
        grouped.setdefault(5 if row["document"] == "credit_note" else 1, []).append(
            {"from": first, "to": last or first, "totnum": int(row["taxable"]), "cancel": 0,
             "net_issue": int(row["taxable"])})
    return [{"doc_num": kind, "docs": [{"num": index, **doc} for index, doc in enumerate(docs, start=1)]}
            for kind, docs in sorted(grouped.items())]


def gstr1_json(supplier_gstin, period, tables):
    by_recipient = {}
    for row in tables.get("b2b", []):
        by_recipient.setdefault(row["recipient_gstin"], []).append(_invoice(row))
    notes = {}
    for row in tables.get("cdnr", []):
        notes.setdefault(row["recipient_gstin"], []).append({
            "ntty": "C", "nt_num": row["document"], "nt_dt": _date(row["date"]), "val": _amount(row["value"]),
            "pos": row["place_of_supply"], "rchrg": "N", "inv_typ": "R", "itms": _items(row)})
    b2cl = {}
    for row in tables.get("b2cl", []):
        invoice = _invoice(row)
        invoice.pop("rchrg")
        invoice.pop("inv_typ")
        b2cl.setdefault(row["place_of_supply"], []).append(invoice)
    supplier_state = supplier_gstin[:2]
    payload = {
        "gstin": supplier_gstin, "fp": period, "version": "GST3.1.6", "hash": "hash",
        "b2b": [{"ctin": ctin, "inv": invoices} for ctin, invoices in sorted(by_recipient.items())],
        "b2cl": [{"pos": pos, "inv": invoices} for pos, invoices in sorted(b2cl.items())],
        "b2cs": [{"sply_ty": "INTRA" if row["place_of_supply"] == supplier_state else "INTER",
                  "pos": row["place_of_supply"], "typ": "OE", "txval": float(Decimal(row["taxable"])),
                  "rt": float(row["rate"]), "iamt": float(row["igst"]), "camt": float(row["cgst"]),
                  "samt": float(row["sgst"]), "csamt": 0} for row in tables.get("b2cs", [])],
        "cdnr": [{"ctin": ctin, "nt": rows} for ctin, rows in sorted(notes.items())],
        "exp": [{"exp_typ": "WOPAY", "inv": [{
            "inum": row["document"], "idt": _date(row["date"]), "val": _amount(row["value"]),
            "itms": [{"txval": _amount(row["taxable"]), "rt": 0, "iamt": 0, "csamt": 0}]}
            for row in tables.get("exp", [])]}] if tables.get("exp") else [],
        "hsn": {"data": [{"num": index, "hsn_sc": row["document"], "desc": "Services", "uqc": "NA",
                          "qty": 0, "val": float(row["value"]), "txval": float(row["taxable"]),
                          "iamt": float(row["igst"]), "camt": float(row["cgst"]), "samt": float(row["sgst"]),
                          "csamt": 0} for index, row in enumerate(tables.get("hsn", []), start=1)]},
        "doc_issue": {"doc_det": _doc_issue(tables.get("docs", []))},
    }
    nil = {}
    for row in tables.get("nil", []):
        bucket = nil.setdefault("INTRAB2C" if row["place_of_supply"] == "intra" else "INTRB2C",
                                {"nil_amt": 0.0, "expt_amt": 0.0, "ngsup_amt": 0.0})
        bucket["expt_amt" if row["document"] == "exempt" else "ngsup_amt"] += float(row["value"])
    payload["nil"] = {"inv": [{"sply_ty": kind, **values} for kind, values in sorted(nil.items())]}
    return payload
