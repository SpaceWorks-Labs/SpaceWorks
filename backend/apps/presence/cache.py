"""Tenant-only TV cache generations; no viewer identity ever enters a key."""
import logging
from uuid import uuid4

from django.core.cache import cache

from .models import PresenceSettings

logger = logging.getLogger(__name__)
TTL = 30


def bump_version(makerspace_id):
    # A database generation participates in the publication transaction, unlike
    # invalidating Redis before a transaction commits (which can refill stale data).
    # Avoid re-creating settings while deleting a tenant/settings row.
    PresenceSettings.objects.filter(makerspace_id=makerspace_id).update(display_version=uuid4())


def read(key):
    try:
        return cache.get(key)
    except Exception:
        logger.warning("presence_cache_read_failed")
        return None


def write(key, payload):
    try:
        cache.set(key, payload, timeout=TTL)
    except Exception:
        logger.warning("presence_cache_write_failed")
