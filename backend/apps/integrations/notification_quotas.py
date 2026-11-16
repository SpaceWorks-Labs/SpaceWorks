"""One addressed reservation per intent; tenant and recipient budgets commit together."""
from django.db import transaction
from django.utils import timezone

from .models_contract import NotificationDelivery
from .models_endpoints import ChannelConfiguration


def reserve(delivery):
    from apps.makerspaces import limits
    with transaction.atomic():
        # Configuration precedes delivery, matching provider destination callbacks.
        config = ChannelConfiguration.objects.select_for_update().filter(
            makerspace=delivery.makerspace, channel=delivery.channel).first()
        row = NotificationDelivery.objects.select_for_update().get(pk=delivery.pk)
        addressed = row.channel in {"sms", "whatsapp"}
        if addressed and row.quota_reserved_at:
            return True
        day = timezone.now().date().isoformat()
        usage = (config.usage if config and config.usage.get("day") == day
            else {"day": day, "total": 0, "recipients": {}})
        key = str(delivery.envelope.recipient_id)
        personal = usage.get("recipients", {}).get(key, 0)
        if config and ((config.quotas.get("daily_limit") and usage["total"] >= config.quotas["daily_limit"])
                or (config.quotas.get("recipient_daily_limit") and personal >= config.quotas["recipient_daily_limit"])):
            return False
        # Check both local limits BEFORE spending the deployment-wide reservation.
        if row.channel not in {"email", "in_app"} and not limits.reserve_notification_quota(delivery.makerspace, row.channel):
            return False
        if config and config.quotas:
            usage["total"] += 1
            usage["recipients"][key] = personal + 1
            config.usage = usage
            config.save(update_fields=["usage", "updated_at"])
        if addressed:
            row.quota_reserved_at = timezone.now()
            row.save(update_fields=["quota_reserved_at", "updated_at"])
            delivery.quota_reserved_at = row.quota_reserved_at
        return True
