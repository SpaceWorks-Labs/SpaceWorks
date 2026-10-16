"""Account for each provider attempt against tenant and sender budgets."""
from django.db import transaction
from django.utils import timezone

from .models_endpoints import ChannelConfiguration


def reserve(delivery):
    from apps.makerspaces import limits
    if delivery.channel not in {"email", "in_app"} and not limits.reserve_notification_quota(delivery.makerspace, delivery.channel):
        return False
    with transaction.atomic():
        config = ChannelConfiguration.objects.select_for_update().filter(
            makerspace=delivery.makerspace, channel=delivery.channel).first()
        if config is None or not config.quotas:
            return True
        # Counters count the day of the ATTEMPT, including retries of an older
        # envelope. The one locked row makes tenant and recipient reservations atomic.
        day = timezone.now().date().isoformat()
        usage = config.usage if config.usage.get("day") == day else {"day": day, "total": 0, "recipients": {}}
        key = str(delivery.envelope.recipient_id)
        personal = usage["recipients"].get(key, 0)
        if ((config.quotas.get("daily_limit") and usage["total"] >= config.quotas["daily_limit"])
                or (config.quotas.get("recipient_daily_limit") and personal >= config.quotas["recipient_daily_limit"])):
            return False
        usage["total"] += 1
        usage["recipients"][key] = personal + 1
        config.usage = usage
        config.save(update_fields=["usage", "updated_at"])
        return True
