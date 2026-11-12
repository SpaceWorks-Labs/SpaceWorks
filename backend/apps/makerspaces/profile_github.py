"""Disposable calendar cache keyed by the live handle/profile generation.

Old workers can write only their old key; readers recompute the key from current
database state. The final check also drops raced results. No tenant rows change.
"""

import hashlib
import json
import logging

from django.core.cache import cache

from .models_account_profile import AccountProfile
from .profile_github_fetch import configured, fetch_calendar, fetch_database_id

logger = logging.getLogger(__name__)
CALENDAR_TTL = 25 * 60 * 60  # Existing refresh task runs daily; cover scheduling jitter.
FAILURE_TTL = 60 * 60
FETCH_LEASE_TTL = 60
REFRESH_INTERVAL = 23 * 60 * 60
VERIFIED_TTL = 7 * 24 * 60 * 60


def current_profile(profile_id):
    return AccountProfile.objects.select_related("user").filter(pk=profile_id).first()


def linked_github_sub(user_id):
    """The immutable GitHub account id the owner signed in with, or None (decision 338, L-P4)."""
    from apps.accounts.models_social import SocialIdentity, SocialProvider

    return SocialIdentity.objects.filter(
        user_id=user_id, provider=SocialProvider.GITHUB).values_list("provider_sub", flat=True).first()


def _verified_key(profile, sub):
    digest = hashlib.sha256(json.dumps([profile.pk, profile.github_username.lower(), sub]).encode()).hexdigest()
    return f"public-profile:github-verified:{digest}"


def github_verified(profile):
    """True only when the username was proven to be the owner's linked GitHub account.

    A cache read, never a network call: `verify_ownership` (the daily refresh) writes it keyed by
    the immutable account id, so a changed username or an unlinked sign-in reads as unverified.
    """
    if not profile.github_username:
        return False
    try:
        sub = linked_github_sub(profile.user_id)
        return bool(sub and cache.get(_verified_key(profile, sub)))
    except Exception:
        logger.warning("public_profile.github_verified_read_failed")
        return False


def verify_ownership(profile):
    """Task-only: compare the username's GitHub account id with the linked sign-in's id."""
    sub = linked_github_sub(profile.user_id)
    if not sub:
        return False
    if github_verified(profile):
        return True
    found = fetch_database_id(profile.github_username)
    if found is None or str(found) != str(sub):
        return False
    try:
        cache.set(_verified_key(profile, sub), True, timeout=VERIFIED_TTL)
    except Exception:
        logger.warning("public_profile.github_verified_write_failed")
    return True


def eligible(profile):
    """Account-level (decision 304c): a listable, visible account that switched the graph on."""
    from .account_profile_read import account_is_listable

    return bool(profile and account_is_listable(profile.user) and profile.is_visible
                and profile.show_activity_graph and profile.github_username
                and github_verified(profile))


def calendar_key(profile):
    # Timestamps supplement the existing on-commit generation invalidation. They prevent ABA changes
    # (alice -> bob -> alice) reusing an in-flight fetch, even if Redis was unavailable at invalidation.
    generation = cache.get(f"public-profile:generation:acct:{profile.user_id}")
    from .account_profile_read import handle_for

    identity = (profile.pk, handle_for(profile.user), profile.updated_at.isoformat(),
                profile.github_username, generation)
    digest = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
    return f"public-profile:github:v2:{digest}"


def calendar_for(profile):
    """Cache-only read after live resolution; outages are an empty calendar."""
    empty = {"source": "github", "days": []}
    if not configured():
        return empty
    current = current_profile(profile.pk)
    if not eligible(current):
        return empty
    try:
        days = cache.get(calendar_key(current))
        return {"source": "github", "days": days if isinstance(days, list) else []}
    except Exception:
        logger.warning("public_profile.github_cache_read_failed")
        return empty


def refresh_calendar(profile_id):
    """Task-only refresh. No network call without a current, eligible profile."""
    if not configured():
        return False
    profile = current_profile(profile_id)
    if profile is None or not verify_ownership(profile) or not eligible(profile):
        # No linked GitHub sign-in for this username: no calendar, and no shared-token spend.
        return False
    try:
        key = calendar_key(profile)
        if cache.get(f"{key}:due") or not cache.add(f"{key}:fetch", True, timeout=FETCH_LEASE_TTL):
            return False
    except Exception:
        logger.warning("public_profile.github_cache_claim_failed")
        return False
    days = fetch_calendar(profile.github_username)
    current = current_profile(profile_id)
    try:
        if not eligible(current) or calendar_key(current) != key:
            return False
        cache.set(key, days if days is not None else [], timeout=CALENDAR_TTL if days is not None else FAILURE_TTL)
        cache.set(f"{key}:due", True, timeout=REFRESH_INTERVAL if days is not None else FAILURE_TTL)
    except Exception:
        logger.warning("public_profile.github_cache_write_failed")
        return False
    return days is not None
