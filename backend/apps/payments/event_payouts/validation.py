"""Model-free checks shared by the core payout command calculations."""

from datetime import datetime
import re


MAX_MINOR = 9_000_000_000_000_000
METHODS = frozenset({"cash", "upi", "bank_transfer", "cheque", "other", "paypal", "wise"})


class PayoutValidationError(ValueError):
    """Safe machine-readable domain failure; never retains rejected values."""

    def __init__(self, code, *, field=None):
        self.code = code
        self.field = field
        super().__init__(code)


def minor(value, *, zero=False, signed=False, field="amount_minor"):
    lower = -MAX_MINOR if signed else (0 if zero else 1)
    if type(value) is not int or not lower <= value <= MAX_MINOR:
        raise PayoutValidationError("invalid_minor_amount", field=field)
    return value


def aware(value, *, field="date"):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise PayoutValidationError("aware_datetime_required", field=field)
    return value


def closed(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise PayoutValidationError("invalid_fields")
    return value


def reason_code(value):
    if not isinstance(value, str) or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value) is None:
        raise PayoutValidationError("invalid_reason_code")
    return value


def reference(value):
    # References are financial metadata. Contacts, bank values and free text belong
    # in the encrypted payee or decision fields, never this immutable receipt.
    if (not isinstance(value, str) or not value.strip() or len(value.strip()) > 64
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise PayoutValidationError("invalid_payout_reference")
    return value.strip()
