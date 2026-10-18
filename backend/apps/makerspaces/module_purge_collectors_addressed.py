"""Adapt provider-owned channel cleanup to the tenant purge result contract."""

from .module_purge_collectors_single_model import _counts


def _delete_channel(makerspace, channel):
    from apps.integrations.messaging.purge import purge_channel

    counts = purge_channel(makerspace, channel)
    # MessagingConsent is portable inert history. Report its label even for an
    # empty queryset so an import's FK-free provenance is removed as well.
    labels = {
        "integrations.MessagingConsent", "integrations.MessagingDelivery",
        "integrations.MessagingWebhookEvent", "integrations.MessagingSenderIdentity",
        "integrations.MessagingSenderCredential",
    }
    if channel == "whatsapp":
        labels.add("integrations.WhatsAppTemplateBinding")
    return _counts(model_labels=labels, **counts)


def sms_delete(makerspace, cursor):
    return _delete_channel(makerspace, "sms")


def whatsapp_delete(makerspace, cursor):
    return _delete_channel(makerspace, "whatsapp")
