"""Display labels (and optional help) for the closed payee-template field keys.

Declared with gettext_noop and translated at the presentation seam, so the descriptor
payload carries ready-to-render text and clients need no key-to-label map of their own.
"""

from django.utils.translation import gettext_noop

from config.locale_resolution import display

FIELD_LABELS = {
    "holder_name": gettext_noop("Account holder name"),
    "account_number": gettext_noop("Account number"),
    "ifsc": gettext_noop("IFSC code"),
    "bank_name": gettext_noop("Bank name"),
    "upi_id": gettext_noop("UPI ID"),
    "routing_number": gettext_noop("Routing number"),
    "account_type": gettext_noop("Account type"),
    "iban": gettext_noop("IBAN"),
    "swift": gettext_noop("SWIFT / BIC"),
    "bsb": gettext_noop("BSB"),
    "institution_number": gettext_noop("Institution number"),
    "transit_number": gettext_noop("Transit number"),
    "bank_code": gettext_noop("Bank code"),
    "branch_code": gettext_noop("Branch code"),
    "payout_email": gettext_noop("Payout email"),
    "delivery_instructions": gettext_noop("Delivery instructions"),
}

FIELD_HELP = {
    "ifsc": gettext_noop("The 11-character code of the bank branch."),
    "bsb": gettext_noop("The six-digit Australian bank-state-branch number."),
    "account_type": gettext_noop("For example checking or savings."),
    "delivery_instructions": gettext_noop("Where and to whom the cheque should be sent."),
}


def field_descriptor(key):
    """`{key, required, label, help}` for one template field; an unknown key is humanised."""
    label = FIELD_LABELS.get(key)
    text = key.replace("_", " ").capitalize()
    return {"key": key, "required": True, "label": display(label) if label else text,
            "help": display(FIELD_HELP.get(key, ""))}
