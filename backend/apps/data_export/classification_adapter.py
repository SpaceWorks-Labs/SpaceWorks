"""Device Adapter API v1 (decisions 310-312): literal export classification.

Except ``ShelfCheck`` (decision 337e: a stock walk is the space's own operational record, so it exports and travels
in a tenant dump; it has no data subject, so it is in no personal export), every adapter model is device-bound
operational state and is OMITTED from exports and tenant dumps: an adapter
re-enrolls and is re-bound on the target, so a moved space never carries a live lease, a status, a calibration
pose (device-specific coordinates, staff-only) or a credential digest (a secret derived from this deployment's key,
meaningless elsewhere). The append-only access and usage logs are evidence for THIS deployment's devices; the
audit trail (which does travel) keeps the decisions' own rows.
"""

from .types import TenantPredicate as P

OMITTED_MODELS = {
    "devices.AdapterProfile": "What a device adapter declared in its last hello; re-sent when it re-enrolls.",
    "devices.AdapterBinding": "Device-bound target bindings; the adapter re-enrolls and staff re-bind on the target.",
    "devices.AdapterStatus": "Latest advisory adapter status, overwritten in place; never tenant history.",
    "devices.AdapterCommand": "Transient command lease queue of a device that re-enrolls on the target.",
    "devices.AdapterEvent": "Raw adapter event stream of this deployment's devices; operational telemetry.",
    "devices.AdapterCredential": "Digest of an NFC tag or PIN keyed by THIS deployment's secret; members re-register.",
    "devices.AdapterPose": "Shelf-pointer calibration coordinates, device-specific and staff-only; re-calibrate.",
    "devices.AdapterAccessLog": "Device access decisions of this deployment's adapters; the audit trail travels.",
    "devices.AdapterUsageLog": "Usage records reported by this deployment's adapters; sessions and charges travel.",
    "devices.AdapterWatch": "Short-lived camera watch session; nothing is retained.",
    "devices.AdapterWebhook": "Push endpoint of a device adapter; its secret is derived from this deployment and is re-issued on re-enrollment.",
    "devices.AdapterWebhookDelivery": "Delivery log of content-free wake-ups to a device adapter of this deployment.",
    "devices.AdapterArtifact": "Private device-uploaded files with retention; bytes are deleted at expiry and on purge.",
    "devices.AdapterTelemetryPoint": "Rolling device telemetry history of this deployment's adapters; bounded by its own sweep.",
    "devices.AdapterTelemetryDrop": "Per-day count of telemetry samples dropped at a limit on this deployment; operational.",
    "devices.AdapterConfigVersion": "Config pushed to a device adapter that re-enrolls on the target; staff push it again.",
    "devices.AdapterAccessCache": "Status of an offline access cache; the digests are rebuilt and signed per device.",
    "devices.AdapterTypeProfile": "Per-machine-type safety defaults for adapter bindings, which are themselves omitted; staff re-enter them.",
}
EXCLUDED_USER_EDGE_REASONS = {
    ("devices.AdapterBinding", "created_by"): "Staff attribution of an omitted device binding.",
    ("devices.AdapterCommand", "created_by"): "Staff attribution of an omitted transient command.",
    ("devices.AdapterCredential", "user"): "Owner of an omitted credential digest.",
    ("devices.AdapterCredential", "created_by"): "Staff attribution of an omitted credential.",
    ("devices.AdapterPose", "saved_by"): "Staff attribution of an omitted calibration pose.",
    ("devices.AdapterAccessLog", "member"): "Member named in an omitted device access log.",
    ("devices.AdapterWatch", "viewer"): "Staff viewer of an omitted watch session.",
    ("devices.AdapterWebhook", "created_by"): "Staff attribution of an omitted push endpoint.",
    ("devices.AdapterConfigVersion", "created_by"): "Staff attribution of an omitted adapter config version.",
    ("devices.AdapterTypeProfile", "updated_by"): "Staff attribution of an omitted safety profile.",
}
# The ShelfCheck author is a live edge (not excluded): the staff member joins the bounded user closure.
RELATIONAL_USER_FIELDS = frozenset(EXCLUDED_USER_EDGE_REASONS) | {("devices.ShelfCheck", "checked_by")}
EXPORTED_FIELDS = {
    "devices.ShelfCheck": "id makerspace checked_by scope_label entries ok_count attention_count created_at",
}
DATASET_SPECS = {"devices.ShelfCheck": ("devices/shelf_checks.csv", P(("makerspace",)))}
# ``entries`` is [{location, status, note}]: storage-location names and staff notes, never an id.
NON_REFERENCE_JSON_FIELDS = frozenset({("devices.ShelfCheck", "entries")})
