"""Integer minor-unit values; the core Payments registry owns currency support."""
from django.core.exceptions import ImproperlyConfigured, ValidationError
from .profile_fields import ProfileValueError

MAX_MINOR = 9_007_199_254_740_991  # Exact across Python and JavaScript JSON clients.


def currency(value):
    try:
        from apps.payments.currencies import normalize_supported_currency
    except ImportError as exc:
        raise ImproperlyConfigured("Install the shared supported-currency contract.") from exc
    try:
        return normalize_supported_currency(value)
    except (ValueError, TypeError, ValidationError) as exc:
        raise ProfileValueError("Select a supported currency.") from exc


def money_schema(raw):
    if (not isinstance(raw, dict) or set(raw) - {"currencies", "min_minor", "max_minor"}
            or not isinstance(raw.get("currencies"), list) or not 1 <= len(raw["currencies"]) <= 100):
        raise ProfileValueError("Configure supported currencies and integer minor-unit bounds.")
    currencies = [currency(item) for item in raw["currencies"]]
    low, high = raw.get("min_minor", 0), raw.get("max_minor", MAX_MINOR)
    if (len(currencies) != len(set(currencies)) or type(low) is not int or type(high) is not int
            or not 0 <= low <= high <= MAX_MINOR):
        raise ProfileValueError("Use unique currencies and ordered nonnegative integer bounds.")
    return {"currencies": currencies, "min_minor": low, "max_minor": high}


def normalize_money(question, value):
    if not isinstance(value, dict) or set(value) != {"amount_minor", "currency"}:
        raise ProfileValueError("Use amount_minor and currency.")
    config, amount = question["money"], value["amount_minor"]
    code = currency(value["currency"])
    if type(amount) is not int or not config["min_minor"] <= amount <= config["max_minor"]:
        raise ProfileValueError("Enter an integer amount within the configured minor-unit bounds.",
                                fields={"amount_minor": ["Amount is outside the allowed integer range."]})
    if code not in config["currencies"]:
        raise ProfileValueError("Select a configured currency.", fields={"currency": ["Currency is not allowed."]})
    return {"amount_minor": amount, "currency": code}
