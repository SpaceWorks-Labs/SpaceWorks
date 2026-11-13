"""Record active app sessions only after native membership validation."""

import logging
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from .models_activity import DeviceActivityDay

logger = logging.getLogger(__name__)


def record_device_activity(grant, membership=None, app_version=""):
    space = membership.makerspace if membership is not None else None
    day = timezone.localdate(timezone.now(), ZoneInfo(space.timezone if space else settings.TIME_ZONE))
    key = f"device-activity:{grant.pk}:{space.pk if space else 'none'}:{day.isoformat()}"
    try:
        if cache.get(key):
            return
    except Exception:
        logger.warning("device_activity_cache_unavailable")
    row, created = DeviceActivityDay.objects.get_or_create(
        grant=grant, makerspace=space, local_day=day,
        defaults={"platform": grant.registration.platform, "app_version": app_version},
    )
    if app_version and row.app_version != app_version:  # the app was updated during the day
        DeviceActivityDay.objects.filter(pk=row.pk).update(app_version=app_version)

    def remember():
        try:
            cache.set(key, True, 300)
        except Exception:
            logger.warning("device_activity_cache_unavailable")
    transaction.on_commit(remember)
