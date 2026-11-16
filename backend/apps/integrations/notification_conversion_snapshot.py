"""Operator checks for the staged conversion, shared with the frozen migration helper."""
import hashlib
import json

from django.apps import apps
from django.core.serializers.json import DjangoJSONEncoder

SNAPSHOT_MODELS = ("MakerspaceMessagingSettings", "WhatsAppTemplateBinding", "MessagingConsent",
    "MessagingDelivery", "ChannelConfiguration", "WhatsAppTemplate", "NotificationDelivery",
    "MessagingWebhookEvent", "MessagingSenderIdentity", "MessagingSenderCredential",
    "PlatformSmsSettings", "PlatformWhatsAppSettings", "NotificationEndpoint", "NotificationEndpointChallenge")


def snapshot(using="default", registry=None):
    registry = registry or apps
    result = {}
    for name in SNAPSHOT_MODELS:
        model = registry.get_model("integrations", name)
        result[name] = snapshot_rows(model.objects.using(using).order_by("pk").values())
    from django.db import connections
    from .migrations._notification_push_snapshot_v1 import snapshot as push_snapshot, empty_snapshot
    result["_push"] = push_snapshot(connections[using]) or empty_snapshot()
    result["_suppression"] = suppression_snapshot(using, registry)
    return result


def suppression_snapshot(using="default", registry=None, maximum=None):
    registry = registry or apps
    rows = registry.get_model("integrations", "MessagingSuppression").objects.using(using).order_by("pk")
    if maximum is not None:
        rows = rows.filter(pk__lte=maximum)
    return snapshot_rows(rows.values("id", "channel", "sender_key", "recipient_hash", "recipient_kind"))


def snapshot_rows(rows):
    digest, count, last_id = hashlib.sha256(), 0, 0
    for row in rows.iterator(chunk_size=500):
        digest.update(json.dumps(row, cls=DjangoJSONEncoder, sort_keys=True).encode())
        count += 1
        last_id = row["id"]
    return {"count": count, "sha256": digest.hexdigest(), "max_id": last_id}


def verify_original_mapping(rows, expected):
    """Compare immutable pre-conversion bytes, including provider/attempt/quota data."""
    from apps.makerspaces.secrets import decrypt_value
    digest, count, maximum = hashlib.sha256(), 0, 0
    for identity, encrypted in rows.order_by("legacy_id").values_list("legacy_id", "snapshot").iterator(chunk_size=500):
        if not encrypted:
            raise ValueError("Original mapping snapshot is missing or privacy-redacted; review is required")
        original = json.loads(decrypt_value(encrypted))
        if expected.get("fields"):
            original = {name: original[name] for name in expected["fields"]}
        digest.update(json.dumps(original, cls=DjangoJSONEncoder, sort_keys=True).encode())
        count += 1
        maximum = identity
    actual = {"count": count, "sha256": digest.hexdigest(), "max_id": maximum}
    if actual != {key: expected[key] for key in actual}:
        raise ValueError("Original mapping snapshots differ from the cutover barrier")


def verify_reconciliation(using="default", registry=None):
    registry = registry or apps
    model = lambda name: registry.get_model("integrations", name).objects.using(using)
    gate = model("NotificationCutover").get(pk=1)
    if not gate.copied_at or gate.sending_enabled:
        raise ValueError("Conversion must be completed while sending remains paused")
    if not all(gate.snapshot.get("_signoffs", {}).get(key) for key in ("producer_coverage", "push", "registries")):
        raise ValueError("Cross-lane contracts have not been signed off")
    if model("NotificationIngress").exclude(state="processed").exists():
        raise ValueError("Unresolved authenticated receipts block retirement/activation")
    if model("NotificationDelivery").filter(state="held").exists():
        raise ValueError("Unknown provider outcomes require evidence before activation")
    if model("NotificationProviderReference").filter(ambiguous=True).exists():
        raise ValueError("Ambiguous physical sender/provider correlation requires review")
    for name in ("MessagingDelivery", "MessagingConsent", "WhatsAppTemplateBinding", "MessagingWebhookEvent",
                 "MakerspaceMessagingSettings.sms", "MakerspaceMessagingSettings.whatsapp",
                 "ChannelConfiguration.T", "NotificationDelivery.T", "WhatsAppTemplate.T"):
        ids = model("NotificationLegacyMapping").filter(legacy_model=name).values_list("legacy_id", flat=True)
        original = gate.snapshot.get(name.split(".")[0], {"max_id": 0, "count": 0})
        if model(name.split(".")[0]).filter(pk__lte=original["max_id"]).exclude(pk__in=ids).exists():
            raise ValueError(f"Unmapped {name} rows block retirement")
        if model("NotificationLegacyMapping").filter(legacy_model=name, legacy_id__lte=original["max_id"]).count() != original["count"]:
            raise ValueError(f"Original {name} mapping count does not match the barrier")
        verify_original_mapping(model("NotificationLegacyMapping").filter(legacy_model=name,
            legacy_id__lte=original["max_id"]), original)
    if model("MessagingDelivery").filter(status__in=["pending", "sending"]).exists():
        raise ValueError("Dispatchable legacy rows remain")
    if model("ChannelConfiguration").filter(channel__in=["sms", "whatsapp"], activation_hold=True,
            enabled=True, personal_enabled=True).exists():
        raise ValueError("Held addressed configuration requires explicit review")
    # The optional inbox app can be absent while its historical table still exists.
    from django.db import connections
    from .migrations._notification_push_snapshot_v1 import has_unmapped
    original = gate.snapshot.get("_push")
    if original is None:
        raise ValueError("Missing original push snapshot")
    if has_unmapped(connections[using], original["max_id"]):
        raise ValueError("Push parent/disposition reconciliation is incomplete")
    if model("NotificationLegacyMapping").filter(legacy_model="MemberPushDelivery", legacy_id__lte=original["max_id"]).count() != original["count"]:
        raise ValueError("Push mapping count does not match the barrier")
    verify_original_mapping(model("NotificationLegacyMapping").filter(legacy_model="MemberPushDelivery",
        legacy_id__lte=original["max_id"]), original)
    original = gate.snapshot.get("_suppression")
    if original and suppression_snapshot(using, registry, original["max_id"]) != original:
        raise ValueError("Sender suppression history changed during conversion")
