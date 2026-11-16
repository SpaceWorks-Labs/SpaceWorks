"""UPI collection details for one charge: the `upi://pay` intent a QR encodes.

Built on the server from the space's billing settings so the browser never assembles
payment instructions itself, and only for an INR charge that is still pending. The
payment note carries a short reference (`SW-<id>`) so staff can match the incoming UPI
credit to the charge; it is the same reference the member's "I've paid" claim shows.
"""

import re
from decimal import Decimal
from urllib.parse import quote

VPA = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-_]{1,255}@[A-Za-z][A-Za-z0-9.\-]{1,63}$")


class UpiError(ValueError):
    pass


def validate_vpa(value):
    vpa = str(value or "").strip()
    if not VPA.fullmatch(vpa) or len(vpa) > 255:
        raise UpiError("Use a UPI ID like name@bank.")
    return vpa


def payment_reference(payment):
    return f"SW-{payment.pk}"


def upi_details(payment, policy):
    """{vpa, payee_name, amount, currency, reference, uri} or None when UPI does not apply."""
    if policy is None or not policy.upi_vpa or payment.currency != "inr" or payment.status != "pending":
        return None
    amount = f"{Decimal(payment.amount):.2f}"
    payee = (policy.upi_payee_name or payment.makerspace.name)[:50]
    reference = payment_reference(payment)
    params = [("pa", policy.upi_vpa), ("pn", payee), ("am", amount), ("cu", "INR"), ("tn", reference)]
    uri = "upi://pay?" + "&".join(f"{key}={quote(str(value), safe='@.-_')}" for key, value in params)
    return {"vpa": policy.upi_vpa, "payee_name": payee, "amount": amount, "currency": "inr",
            "reference": reference, "uri": uri}
