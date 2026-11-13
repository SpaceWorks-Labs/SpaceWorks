"""Withdrawal hooks shared by future share-card and sitemap adapters.

Public reads always check live predicates and send no-store. A cached card is never
authorization; adapters must resolve_public_profile before consulting a cached body.
"""

import uuid
import logging
import hashlib
import json
from dataclasses import asdict
from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_save, post_delete

logger = logging.getLogger(__name__)
# A generation only has to outlive the entries it versions (the GitHub calendar, 25 hours); a key with
# no expiry per profile would grow with every profile ever edited (decision 339).
GENERATION_TTL = 8 * 24 * 60 * 60


def invalidate_profile(profile_id):
    if profile_id is None:
        return
    def invalidate():
        try:
            body_key = cache.get(f"public-profile:share:{profile_id}")
            if isinstance(body_key, str) and body_key.startswith("website-share:v1:"):
                cache.delete(body_key)
            cache.set(f"public-profile:generation:{profile_id}", uuid.uuid4().hex, timeout=GENERATION_TTL)
            cache.delete_many([f"public-profile:share:{profile_id}", "public-profile:sitemap"])
            cache.set("public-profile:sitemap-generation", uuid.uuid4().hex, timeout=GENERATION_TTL)
        except Exception:
            # Consent has already committed. All adapters must still run the live
            # predicate before reading cache; a failed Redis cannot revive consent.
            logger.exception("public_profile.cache_invalidation_failed", extra={"profile_id": profile_id})
    transaction.on_commit(invalidate)


def remember_share_card(profile_id, card):
    """Index the shared renderer's actual body key so withdrawal deletes it too."""
    digest = hashlib.sha256(json.dumps(asdict(card), sort_keys=True).encode()).hexdigest()
    try:
        cache.set(f"public-profile:share:{profile_id}", f"website-share:v1:{digest}", timeout=600)
    except Exception:
        logger.exception("public_profile.share_cache_unavailable", extra={"profile_id": profile_id})


def invalidate_account(user_id):
    """Account-level key: the global profile is cached per account, not per membership."""
    invalidate_profile(f"acct:{user_id}")


def register_signals():
    from .models import Makerspace, MakerspaceMembership
    from .models_account_profile import AccountProfile, AccountProject, AccountTimelineEntry, ProfileAchievement
    from .models_profiles import MemberProfile, MemberProject, ProfileTimelineEntry, PublicHandle
    from django.contrib.auth import get_user_model

    def changed(sender, instance, **kwargs):
        if sender in (AccountProfile, PublicHandle, MakerspaceMembership):
            users = [instance.user_id]
        elif sender in (AccountProject, AccountTimelineEntry, ProfileAchievement):
            users = [instance.profile.user_id]
        elif sender is Makerspace:
            users = MakerspaceMembership.all_tracks.filter(makerspace=instance).values_list("user_id", flat=True)
        elif sender is get_user_model():
            users = [instance.pk]
        else:
            users = []
        for pk in set(users):
            invalidate_account(pk)
        # Legacy per-membership rows still drive the old share cache keys.
        if sender is MemberProfile:
            invalidate_profile(instance.pk)
        elif sender in (MemberProject, ProfileTimelineEntry):
            invalidate_profile(instance.profile_id)
        elif sender is PublicHandle:
            invalidate_profile(instance.profile_id)

    for model in (AccountProfile, AccountProject, AccountTimelineEntry, ProfileAchievement, PublicHandle,
                  MemberProfile, MemberProject, ProfileTimelineEntry, MakerspaceMembership, Makerspace,
                  get_user_model()):
        for signal in (post_save, post_delete):
            signal.connect(changed, sender=model, weak=False,
                           dispatch_uid=f"public-profile:{signal}:{model._meta.label}")
