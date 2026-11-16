"""Parity E-B8 tenant-dump field snapshot: see ``data_export.classification_e_b8`` for the reasons."""

EXTRA_FIELDS = {
    "integrations.NotificationDestination": frozenset({"previous_signing_secret", "previous_secret_valid_until"}),
    "makerspaces.Makerspace": frozenset({"email_from_name", "email_reply_to", "smtp_verified_fingerprint",
                                         "smtp_verified_at"}),
}
FIELD_NAMES = {
    "integrations.PlatformLegalPage": frozenset("id slug language markdown updated_at".split()),
}
