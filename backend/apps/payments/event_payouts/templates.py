"""Closed, versioned routing templates. Values never enter audit or exports.

The finance policy must enable the country/method before this validator is called.
No tax identifiers, card details, credentials or Saved-details inputs are accepted.
"""

import re

from .validation import PayoutValidationError, closed


TEMPLATE_VERSION = 1
IBAN_LENGTHS = {"AT": 20, "BE": 16, "CH": 21, "DE": 22, "DK": 18, "ES": 24,
                "FI": 18, "FR": 27, "GB": 22, "IE": 22, "IT": 27, "NL": 18,
                "NO": 15, "PL": 28, "PT": 25, "SE": 24}
COUNTRIES = frozenset({"IN", "US", "AU", "CA", "NZ", *IBAN_LENGTHS})
ROUTING_FIELDS = {
    "in_bank": ("holder_name", "account_number", "ifsc", "bank_name"),
    "in_upi": ("holder_name", "upi_id"),
    "us_bank": ("holder_name", "routing_number", "account_number", "account_type"),
    "iban_bank": ("holder_name", "iban", "swift", "bank_name"),
    "au_bank": ("holder_name", "bank_name", "account_number", "bsb", "swift"),
    "ca_bank": ("holder_name", "bank_name", "account_number", "institution_number", "transit_number", "swift"),
    "nz_bank": ("holder_name", "bank_name", "account_number", "bank_code", "branch_code", "swift"),
    "email": ("holder_name", "payout_email"),
    "cash": ("holder_name",),
    "cheque": ("holder_name", "delivery_instructions"),
    "other": ("holder_name",),
}


def _text(value, maximum=200):
    if (not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise PayoutValidationError("invalid_payee_details")
    return value.strip()


def _digits(value, low, high):
    value = _text(value, high)
    if not value.isascii() or not value.isdigit() or not low <= len(value) <= high:
        raise PayoutValidationError("invalid_payee_details")
    return value


def _pattern(value, pattern):
    value = _text(value)
    if re.fullmatch(pattern, value, flags=re.ASCII) is None:
        raise PayoutValidationError("invalid_payee_details")
    return value


def template_key(country, method):
    if not isinstance(country, str) or not isinstance(method, str) or country not in COUNTRIES:
        raise PayoutValidationError("payee_template_unsupported")
    if method in {"cash", "cheque", "other"}:
        return method
    if method in {"paypal", "wise"}:
        return "email"
    if country == "IN" and method == "upi":
        return "in_upi"
    if method == "bank_transfer":
        if country == "IN":
            return "in_bank"
        if country == "US":
            return "us_bank"
        if country in {"AU", "CA", "NZ"}:
            return country.lower() + "_bank"
        if country in IBAN_LENGTHS:
            return "iban_bank"
    raise PayoutValidationError("payee_template_unsupported")


def validate_details(*, country, method, template, version, details, enabled_templates):
    expected = template_key(country, method)
    if type(version) is not int or version != TEMPLATE_VERSION or template != expected:
        raise PayoutValidationError("payee_template_changed")
    if (country, method, template, version) not in enabled_templates:
        raise PayoutValidationError("payee_template_disabled")
    closed(details, ROUTING_FIELDS[expected])
    result = {key: _text(value, 1000 if key == "delivery_instructions" else 200)
              for key, value in details.items()}
    if expected == "in_bank":
        result["account_number"] = _digits(details["account_number"], 6, 34)
        result["ifsc"] = _pattern(result["ifsc"].upper(), r"[A-Z]{4}0[A-Z0-9]{6}")
    elif expected == "in_upi":
        result["upi_id"] = _pattern(result["upi_id"], r"[A-Za-z0-9._-]{2,128}@[A-Za-z][A-Za-z0-9.-]{1,63}")
    elif expected == "us_bank":
        number = _digits(details["routing_number"], 9, 9)
        if number == "000000000" or sum(int(digit) * weight for digit, weight in zip(number, (3, 7, 1) * 3)) % 10:
            raise PayoutValidationError("invalid_payee_details")
        result["routing_number"] = number
        result["account_number"] = _digits(details["account_number"], 4, 17)
        if result["account_type"] not in {"checking", "savings"}:
            raise PayoutValidationError("invalid_payee_details")
    elif expected == "iban_bank":
        iban = result["iban"].replace(" ", "").upper()
        if len(iban) != IBAN_LENGTHS[country] or re.fullmatch(r"[A-Z]{2}[0-9]{2}[A-Z0-9]+", iban, re.ASCII) is None:
            raise PayoutValidationError("invalid_payee_details")
        if iban[:2] != country:
            raise PayoutValidationError("invalid_payee_details")
        check = "".join(str(ord(char) - 55) if char.isalpha() else char for char in iban[4:] + iban[:4])
        if int(check) % 97 != 1:
            raise PayoutValidationError("invalid_payee_details")
        result["iban"] = iban
        result["swift"] = _pattern(result["swift"].upper(), r"[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?")
        if result["swift"][4:6] != country:
            raise PayoutValidationError("invalid_payee_details")
    elif expected in {"au_bank", "ca_bank", "nz_bank"}:
        result["account_number"] = _digits(details["account_number"], 4, 34)
        lengths = {"au_bank": {"bsb": 6}, "ca_bank": {"institution_number": 3, "transit_number": 5},
                   "nz_bank": {"bank_code": 2, "branch_code": 4}}[expected]
        for field, length in lengths.items():
            result[field] = _digits(details[field], length, length)
        result["swift"] = _pattern(result["swift"].upper(), r"[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?")
        if result["swift"][4:6] != country:
            raise PayoutValidationError("invalid_payee_details")
    elif expected == "email":
        from django.core.exceptions import ValidationError
        from django.core.validators import validate_email
        try:
            validate_email(result["payout_email"])
        except ValidationError:
            raise PayoutValidationError("invalid_payee_details") from None
        local, domain = result["payout_email"].rsplit("@", 1)
        result["payout_email"] = local + "@" + domain.lower()
    return result


def masked_details(details, *, country, method):
    """Call only after owner/finance authorization and tenant decryption."""
    key = template_key(country, method)
    if key in {"in_bank", "us_bank", "au_bank", "ca_bank", "nz_bank"}:
        return "••••" + details["account_number"][-4:]
    if key == "iban_bank":
        return "••••" + details["iban"][-4:]
    if key == "in_upi":
        return "••••" + details["upi_id"][-4:]
    if key == "email":
        return "••••@••••"
    return "Routing details hidden"
