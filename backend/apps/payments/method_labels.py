"""Display labels for how a member paid online ("Visa ••4242", "UPI 98••••10@ybl").

Built only from the brand and last four digits a provider already masks, never from a
full card number, expiry or CVC (providers never send those to a webhook). A UPI handle
that embeds a phone number is masked down to its first and last two characters, so the
receipt identifies the payer's own handle without printing their number.
"""

import re

NETWORKS = {"visa": "Visa", "mastercard": "Mastercard", "amex": "Amex", "american_express": "Amex",
            "rupay": "RuPay", "discover": "Discover", "diners": "Diners", "jcb": "JCB", "unionpay": "UnionPay",
            "maestro": "Maestro"}


def _card(network, last4):
    last4 = re.sub(r"\D", "", str(last4 or ""))[-4:]
    name = NETWORKS.get(str(network or "").lower().replace(" ", "_"), str(network or "Card").title())
    return f"{name} ••{last4}" if len(last4) == 4 else name


def mask_vpa(vpa):
    vpa = str(vpa or "").strip()
    if "@" not in vpa:
        return ""
    local, _, bank = vpa.partition("@")
    if sum(char.isdigit() for char in local) >= 6 and len(local) > 4:
        local = f"{local[:2]}{'•' * (len(local) - 4)}{local[-2:]}"
    return f"{local}@{bank}"[:56]


def stripe_label(obj):
    """From a Charge, or a PaymentIntent carrying its charge (`charges.data[0]` / `latest_charge`)."""
    if not isinstance(obj, dict):
        return ""
    charge = obj
    if "payment_method_details" not in obj:
        latest = obj.get("latest_charge")
        charges = (obj.get("charges") or {}).get("data") or []
        charge = latest if isinstance(latest, dict) else (charges[0] if charges else {})
    details = (charge or {}).get("payment_method_details") or {}
    kind = details.get("type") or ""
    if kind == "card":
        card = details.get("card") or {}
        return _card(card.get("brand"), card.get("last4"))
    if kind == "upi":
        return f"UPI {mask_vpa((details.get('upi') or {}).get('vpa'))}".strip()
    return kind.replace("_", " ").title()[:64] if kind else ""


def razorpay_label(entity):
    if not isinstance(entity, dict):
        return ""
    method = entity.get("method") or ""
    if method == "card":
        card = entity.get("card") or {}
        return _card(card.get("network"), card.get("last4"))
    if method == "upi":
        handle = mask_vpa(entity.get("vpa") or (entity.get("upi") or {}).get("vpa"))
        return f"UPI {handle}".strip()
    if method == "netbanking":
        return f"Net banking {entity.get('bank') or ''}".strip()[:64]
    if method == "wallet":
        return f"Wallet {entity.get('wallet') or ''}".strip()[:64]
    return method.replace("_", " ").title()[:64]
