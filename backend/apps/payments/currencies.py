"""Supported tender currencies for new money contracts (legacy ledger unchanged)."""

from .money import minor_unit_exponent

# Version 1 includes only currencies correctly scaled by money.py. Funds, metals,
# test/no-currency codes and unsupported scales (including IQD/LYD/ISK) are absent.
SUPPORTED_CURRENCIES_VERSION = 1
SUPPORTED_CURRENCIES = frozenset("""
AED AFN ALL AMD AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND
BOB BRL BSD BTN BWP BYN BZD CAD CDF CHF CLP CNY COP CRC CUP CVE CZK DJF
DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD
HKD HNL HTG HUF IDR ILS INR IRR JMD JOD JPY KES KGS KHR KMF KPW KRW
KWD KYD KZT LAK LBP LKR LRD LSL MAD MDL MKD MMK MNT MOP MRU MUR
MVR MWK MXN MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR
PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SOS SRD
SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS UAH UGX USD
UYU UZS VES VND VUV WST XAF XCD XCG XOF XPF YER ZAR ZMW ZWG
""".split())


def normalize_supported_currency(value):
    """Return uppercase wire spelling; reject unknowns before exponent lookup."""
    if not isinstance(value, str):
        raise ValueError("unsupported_currency")
    code = value.strip()
    if len(code) != 3 or not code.isascii() or not code.isalpha():
        raise ValueError("unsupported_currency")
    code = code.upper()
    if code not in SUPPORTED_CURRENCIES:
        raise ValueError("unsupported_currency")
    return code


def supported_minor_unit_exponent(value):
    return minor_unit_exponent(normalize_supported_currency(value).lower())
