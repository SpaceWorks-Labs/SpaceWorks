"""Counts from both per-device push ledgers, with bounded platform/status labels."""

from collections import Counter

from django.db.models import Count


def push_outcome_samples():
    from apps.integrations.models_tracking import PushDeliveryAttempt
    from apps.notifications.models_push import MemberPushDelivery

    counts = Counter()
    for model in (PushDeliveryAttempt, MemberPushDelivery):
        for row in model.objects.order_by().values("platform", "status").annotate(count=Count("pk")):
            platform = row["platform"] if row["platform"] in ("apple", "android") else "unknown"
            status = row["status"] if row["status"] in ("pending", "sending", "sent", "failed", "skipped") else "unknown"
            counts[(platform, status)] += row["count"]
    return [({"platform": platform, "status": status}, count) for (platform, status), count in sorted(counts.items())]
