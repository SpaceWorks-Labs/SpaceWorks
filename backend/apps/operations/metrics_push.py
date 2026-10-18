"""Counts from both per-device push ledgers, with bounded platform/status labels."""

from collections import Counter

from django.apps import apps
from django.db.models import Count


def push_outcome_samples():
    from apps.integrations.models_tracking import PushDeliveryAttempt
    counts = Counter()
    models = [PushDeliveryAttempt]
    if apps.is_installed("apps.notifications"):
        models.append(apps.get_model("notifications", "MemberPushDelivery"))
    for model in models:
        for row in model.objects.order_by().values("platform", "status").annotate(count=Count("pk")):
            platform = row["platform"] if row["platform"] in ("apple", "android") else "unknown"
            status = row["status"] if row["status"] in ("pending", "sending", "sent", "failed", "skipped", "held", "canceled") else "unknown"
            counts[(platform, status)] += row["count"]
    return [({"platform": platform, "status": status}, count) for (platform, status), count in sorted(counts.items())]
