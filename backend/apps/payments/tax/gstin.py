"""GSTIN format, state-prefix and check-character validation.

A GSTIN is 15 characters: a two-digit state code, the holder's ten-character PAN, an
entity number, the letter Z (reserved) and a check character. The check character is the
mod-36 Luhn variant GSTN publishes: weights alternate 1 and 2 from the left, each product
contributes its base-36 quotient plus remainder, and the check digit tops the sum up to a
multiple of 36. A typo in any one character fails it, which is the point -- a wrong GSTIN
on a B2B tax invoice denies the buyer their input credit.
"""

import re

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")

#: GSTN state and union-territory codes (place-of-supply codes).
STATE_NAMES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu", "27": "Maharashtra", "29": "Karnataka",
    "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry",
    "35": "Andaman and Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh",
    "97": "Other Territory",
}
#: Union territories without a legislature levy UTGST in place of SGST.
UTGST_STATES = frozenset({"04", "26", "31", "35", "38", "97"})


class GstinError(ValueError):
    def __init__(self, message, code="gstin_invalid"):
        super().__init__(message)
        self.code = code


def normalize(value):
    return re.sub(r"\s+", "", str(value or "")).upper()


def check_character(first_fourteen):
    total = 0
    for index, char in enumerate(first_fourteen):
        product = ALPHABET.index(char) * (1 if index % 2 == 0 else 2)
        total += product // 36 + product % 36
    return ALPHABET[(36 - total % 36) % 36]


def validate_gstin(value):
    """Return the normalized GSTIN or raise GstinError naming what is wrong."""
    gstin = normalize(value)
    if not PATTERN.fullmatch(gstin):
        raise GstinError("A GSTIN is 15 characters: state code, PAN, entity number, Z and a check character.")
    if gstin[:2] not in STATE_NAMES:
        raise GstinError("The GSTIN does not start with a recognised state code.")
    if check_character(gstin[:14]) != gstin[14]:
        raise GstinError("The GSTIN check character does not match; check for a typo.")
    return gstin


def is_valid_gstin(value):
    try:
        validate_gstin(value)
    except GstinError:
        return False
    return True


def validate_state_code(value):
    code = str(value or "").strip().zfill(2)
    if code not in STATE_NAMES:
        raise GstinError("Use a two-digit GST state code.", code="state_code_invalid")
    return code


def state_label(code):
    return f"{code}-{STATE_NAMES[code]}" if code in STATE_NAMES else code
