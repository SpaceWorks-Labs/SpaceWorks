"""Deployment-keyed recipient hashes and the common suppression lookup."""
from django.db.models import Q
from django.utils.crypto import salted_hmac

from apps.integrations.models import MessagingRecipientAlias, MessagingSuppression
from .locks import advisory_lock


def recipient_hash(kind, value):
    if kind not in {"phone", "alias"}:
        raise ValueError("Recipient hashes use provider identities only.")
    return salted_hmac("spaceworks.messaging.suppression.v1", f"{kind}:{value}", algorithm="sha256").hexdigest()


def lock_suppression_key(channel, sender_key, phone_hash):
    advisory_lock(f"messaging-suppression:{channel}:{sender_key}:{phone_hash}")


def suppression_rows(channel, sender_key, phone_hash):
    aliases = MessagingRecipientAlias.objects.filter(
        channel=channel, sender_key=sender_key, phone_hash=phone_hash,
    ).values("alias_hash")
    return MessagingSuppression.objects.filter(channel=channel, sender_key=sender_key,
        lifted_at__isnull=True).filter(Q(recipient_hash=phone_hash) | Q(recipient_hash__in=aliases))


def suppressed(channel, sender_key, phone_hash):
    return (MessagingSuppression.objects.filter(channel=channel, sender_key=sender_key,
        recipient_kind="sender", lifted_at=None).exists()
        or suppression_rows(channel, sender_key, phone_hash).exists())


def unmapped_alias_suppressions(sender_key):
    """Caller takes lock_whatsapp_sender before inspecting this sender-wide state."""
    mapped = MessagingRecipientAlias.objects.filter(channel="whatsapp", sender_key=sender_key).values("alias_hash")
    return MessagingSuppression.objects.filter(channel="whatsapp", sender_key=sender_key,
        recipient_kind="alias", lifted_at__isnull=True).exclude(recipient_hash__in=mapped)
