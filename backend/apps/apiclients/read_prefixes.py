"""Mandatory read-protocol prefixes, safe to import while settings are built."""


def mandatory_hmac_prefixes():
    from apps.separability.tombstones import tombstoned_app_labels
    return [] if "events" in tombstoned_app_labels() else ["/api/v1/events/"]


def requires_signed_read(path):
    return any(path.startswith(prefix) for prefix in mandatory_hmac_prefixes())
