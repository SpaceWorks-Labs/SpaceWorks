"""Disposable calendar cache keyed by the live handle/profile generation.

Old workers can write only their old key; readers recompute the key from current
database state. The final check also drops raced results. No tenant rows change.
"""

import hashlib
import json
import logging

from django.core.cache import cache

from .models_profiles import PublicHandle
from .profile_github_fetch import configured, fetch_calendar
from .public_profile_access import profile_is_public

logger = logging.getLogger(__name__)
CALENDAR_TTL = 25 * 60 * 60  # Existing refresh task runs daily; cover scheduling jitter.
FAILURE_TTL = 60 * 60
FETCH_LEASE_TTL = 60
REFRESH_INTERVAL = 23 * 60 * 60


def current_claim(claim_id):
    return PublicHandle.objects.select_related(
        "profile__membership__user", "profile__membership__makerspace",
    ).filter(pk=claim_id).first()


def eligible(claim):
    return bool(claim and claim.user_id == claim.profile.membership.user_id
                and profile_is_public(claim.profile) and claim.profile.show_activity_graph
                and claim.profile.github_username)


def calendar_key(claim):
    profile = claim.profile
    # Timestamps supplement the existing on-commit generation invalidation. They
    # prevent ABA changes (alice -> bob -> alice) reusing an in-flight fetch, even
    # if Redis was unavailable at invalidation time.
    generation = cache.get(f"public-profile:generation:{profile.pk}")
    identity = (claim.pk, claim.handle, claim.changed_at.isoformat(), profile.pk,
                profile.updated_at.isoformat(), profile.github_username, generation)
    digest = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
    return f"public-profile:github:v1:{digest}"


def calendar_for(claim):
    """Cache-only read after live public resolution; outages are an empty calendar."""
    empty = {"source": "github", "days": []}
    if not configured():
        return empty
    current = current_claim(claim.pk)
    if not eligible(current) or current.handle != claim.handle or current.profile_id != claim.profile_id:
        return empty
    try:
        days = cache.get(calendar_key(current))
        return {"source": "github", "days": days if isinstance(days, list) else []}
    except Exception:
        logger.warning("public_profile.github_cache_read_failed")
        return empty


def refresh_calendar(claim_id):
    """Task-only refresh. No network call without current publication + graph consent."""
    if not configured():
        return False
    claim = current_claim(claim_id)
    if not eligible(claim):
        return False
    try:
        key = calendar_key(claim)
        if cache.get(f"{key}:due") or not cache.add(f"{key}:fetch", True, timeout=FETCH_LEASE_TTL):
            return False
    except Exception:
        logger.warning("public_profile.github_cache_claim_failed")
        return False
    days = fetch_calendar(claim.profile.github_username)
    current = current_claim(claim_id)
    try:
        if not eligible(current) or calendar_key(current) != key:
            return False
        cache.set(key, days if days is not None else [], timeout=CALENDAR_TTL if days is not None else FAILURE_TTL)
        cache.set(f"{key}:due", True, timeout=REFRESH_INTERVAL if days is not None else FAILURE_TTL)
    except Exception:
        logger.warning("public_profile.github_cache_write_failed")
        return False
    return days is not None
