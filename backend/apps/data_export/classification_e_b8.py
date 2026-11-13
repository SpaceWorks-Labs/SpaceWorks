"""Parity E-B8 export classification.

* ``NotificationDestination.previous_signing_secret`` is the retiring webhook secret: ciphertext, always omitted,
  exactly like ``signing_secret``. Its expiry timestamp is a plain date.
* ``Makerspace.email_from_name`` / ``email_reply_to`` are a space's own sender settings and travel with it.
  ``smtp_verified_fingerprint`` / ``smtp_verified_at`` only record that the space's SMTP settings passed a test; the
  hash covers those settings, so on a target (where the SMTP account is reset) it never matches and proves nothing.
* ``integrations.PlatformLegalPage`` is the operator's privacy / terms text: platform governance, never tenant data.
"""

EXTRA_FIELDS = {
    "integrations.NotificationDestination": "previous_signing_secret previous_secret_valid_until",
    "makerspaces.Makerspace": "email_from_name email_reply_to smtp_verified_fingerprint smtp_verified_at",
}
OMITTED_MODELS = {
    "integrations.PlatformLegalPage": "The platform operator's privacy / terms text; deployment-level, not tenant data.",
}
ALWAYS_OMITTED = {
    ("integrations.NotificationDestination", "previous_signing_secret"): "Encrypted retiring webhook signing secret.",
}
NON_CREDENTIAL = {
    ("integrations.NotificationDestination", "previous_secret_valid_until"):
        "Expiry timestamp of the rotation grace window; the secret itself is omitted.",
}


def extend(fields):
    for label, extra in EXTRA_FIELDS.items():
        fields[label] += " " + extra
    return fields
