"""Read the same counters and limits used by quota enforcement."""

from django.conf import settings
from django.utils import timezone

from apps.makerspaces import limits
from apps.makerspaces.limits_usage import _COUNTERS

COUNTER_APPS = {"events": "events", "bookings": "bookings"}


def usage_snapshot(makerspace):
    from apps.integrations.models import DailyNotificationCounter

    notifications = dict(DailyNotificationCounter.objects.filter(
        makerspace=makerspace, day=timezone.now().date(),
    ).values_list("channel", "count"))
    from apps.makerspaces.limit_registry import area_of
    from apps.managed_hosting.limit_catalogue import NEW_KEYS, effective_limit, label_of, registry_keys, unit_of, used_of

    resources = []
    # Owner rule 261: every registry key, grouped by console area (not only the old numeric keys).
    for key in registry_keys():
        if key in NEW_KEYS:
            limit = effective_limit(makerspace, key)
            # The new keys are counted only while limited: a snapshot runs per space on dashboards.
            used = used_of(makerspace, key) if limit is not None else None
        else:
            counter = _COUNTERS.get(key)
            if COUNTER_APPS.get(key) in settings.TOMBSTONED_APPS or key in limits.CAP_LIMIT_KEYS:
                used = None  # a per-file cap has nothing to count
            else:
                used = counter(makerspace) if counter else notifications.get(key, 0)
            limit = limits.resource_limit(makerspace, key)
        resources.append({
            "key": key, "label": label_of(key), "area": area_of(key),
            "used": used, "limit": limit, "unit": unit_of(key),
        })
    return {
        "makerspace_id": makerspace.pk,
        "managed": not limits.is_self_host(),
        "resources": resources,
    }
