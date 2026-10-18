"""Frozen row fingerprint algorithm for the expand/convert checkpoint."""
import hashlib
import json

from django.core.serializers.json import DjangoJSONEncoder

MODELS = ("MakerspaceMessagingSettings", "WhatsAppTemplateBinding", "MessagingConsent",
    "MessagingDelivery", "ChannelConfiguration", "WhatsAppTemplate", "NotificationDelivery",
    "MessagingWebhookEvent", "MessagingSenderIdentity", "MessagingSenderCredential",
    "PlatformSmsSettings", "PlatformWhatsAppSettings", "NotificationEndpoint", "NotificationEndpointChallenge")


def snapshot(registry, alias):
    result = {}
    for name in MODELS:
        digest, count, last_id = hashlib.sha256(), 0, 0
        model = registry.get_model("integrations", name)
        for row in model.objects.using(alias).order_by("pk").values().iterator(chunk_size=500):
            digest.update(json.dumps(row, cls=DjangoJSONEncoder, sort_keys=True).encode())
            count += 1
            last_id = row["id"]
        result[name] = {"count": count, "sha256": digest.hexdigest(), "max_id": last_id}
    digest, count, last_id = hashlib.sha256(), 0, 0
    for row in registry.get_model("integrations", "MessagingSuppression").objects.using(alias).order_by("pk").values(
            "id", "channel", "sender_key", "recipient_hash", "recipient_kind").iterator(chunk_size=500):
        digest.update(json.dumps(row, cls=DjangoJSONEncoder, sort_keys=True).encode())
        count += 1
        last_id = row["id"]
    result["_suppression"] = {"count": count, "sha256": digest.hexdigest(), "max_id": last_id}
    return result
