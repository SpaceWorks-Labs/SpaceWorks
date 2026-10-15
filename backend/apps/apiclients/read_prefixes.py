"""Mandatory read-protocol prefixes, safe to import while settings are built."""


def mandatory_hmac_prefixes():
    from .scope_registry_booking_reads import PREFIX, booking_read_scopes
    from apps.separability.tombstones import tombstoned_app_labels
    return (([] if "events" in tombstoned_app_labels() else ["/api/v1/events/"])
            + ([PREFIX] if booking_read_scopes() else []))


def requires_signed_read(path):
    return any(path.startswith(prefix) for prefix in mandatory_hmac_prefixes())
