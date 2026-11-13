"""Verify a GitHub username right after it changes, instead of waiting for the daily sweep (decision 338).

Three triggers, one task: a GitHub sign-in is linked, a GitHub sign-in is unlinked, and the profile's
`github_username` is saved. Linking and saving queue the task after commit, deduplicated for a minute.
Unlinking already fails closed on every read (`github_verified` requires a live link), so it only drops the
cached public payload. Nothing here runs a network call in a request.
"""

import logging

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save

logger = logging.getLogger(__name__)
DEDUPE_TTL = 60


def queue_verification(user_id):
    """Queue one verify-and-refresh for this account once the surrounding transaction commits."""
    transaction.on_commit(lambda: _dispatch(user_id))


def _dispatch(user_id):
    from apps.operations.durable_dispatch import resident_delivery

    if not resident_delivery():
        # No worker (cron mode, brokerless cloud): .delay() would run the GitHub call inline in this
        # request. The daily refresh verifies instead (decision 339).
        return
    try:
        if not cache.add(f"public-profile:github-verify-queued:{user_id}", True, timeout=DEDUPE_TTL):
            return
    except Exception:
        logger.warning("public_profile.github_verify_dedupe_unavailable")  # better a duplicate than a miss
    try:
        from .tasks import verify_github_ownership_task
        verify_github_ownership_task.delay(user_id)
    except Exception:
        logger.warning("public_profile.github_verify_enqueue_failed")  # the daily sweep still verifies


def _is_github(instance):
    return instance.provider == "github"


def register_signals():
    from apps.accounts.models_social import SocialIdentity

    from .public_profile_cache import invalidate_account

    def linked(sender, instance, **kwargs):
        if _is_github(instance):
            invalidate_account(instance.user_id)
            queue_verification(instance.user_id)

    def unlinked(sender, instance, **kwargs):
        if _is_github(instance):
            invalidate_account(instance.user_id)

    post_save.connect(linked, sender=SocialIdentity, dispatch_uid="github-identity-linked")
    post_delete.connect(unlinked, sender=SocialIdentity, dispatch_uid="github-identity-unlinked")
