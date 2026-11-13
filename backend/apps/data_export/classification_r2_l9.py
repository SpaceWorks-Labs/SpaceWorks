"""Release-2 lane L9 (phase 8 i18n): literal export classification.

``Makerspace.default_locale`` is a plain settings column (a locale code from the registry:
non-PII, non-secret, never a reference) and exports with the space. The account's own
``User.preferred_locale`` travels in the user projection (``data_export/fields.py``).
"""

EXTRA_FIELDS = {
    "makerspaces.Makerspace": "default_locale",
}


def extend(fields):
    for label, extra in EXTRA_FIELDS.items():
        fields[label] += " " + extra
    return fields
