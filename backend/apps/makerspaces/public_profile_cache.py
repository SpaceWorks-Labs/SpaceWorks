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


def invalidate_profile(profile_id):
    def invalidate():
        try:
            body_key = cache.get(f"public-profile:share:{profile_id}")
            if isinstance(body_key, str) and body_key.startswith("website-share:v1:"):
                cache.delete(body_key)
            cache.set(f"public-profile:generation:{profile_id}", uuid.uuid4().hex, timeout=None)
            cache.delete_many([f"public-profile:share:{profile_id}", "public-profile:sitemap"])
            cache.set("public-profile:sitemap-generation", uuid.uuid4().hex, timeout=None)
        except Exception:
            # Consent has already committed. All adapters must still run the live
            # predicate before reading cache; a failed Redis cannot revive consent.
            logger.exception("public_profile.cache_invalidation_failed", extra={"profile_id": profile_id})
    transaction.on_commit(invalidate)


def remember_share_card(profile_id, card):
    """Index the shared renderer's actual body key so withdrawal deletes it too."""
    digest = hashlib.sha256(json.dumps(asdict(card), sort_keys=True).encode()).hexdigest()
    cache.set(f"public-profile:share:{profile_id}", f"website-share:v1:{digest}", timeout=600)


def register_signals():
    from .models import Makerspace, MakerspaceMembership
    from .models_profiles import MemberProfile, MemberProject, ProfileTimelineEntry, PublicHandle
    from django.contrib.auth import get_user_model

    def changed(sender, instance, **kwargs):
        if sender is MemberProfile:
            ids = [instance.pk]
        elif sender in (MemberProject, ProfileTimelineEntry, PublicHandle):
            ids = [instance.profile_id]
        elif sender is MakerspaceMembership:
            ids = MemberProfile.objects.filter(membership=instance).values_list("pk", flat=True)
        elif sender is Makerspace:
            ids = MemberProfile.objects.filter(membership__makerspace=instance).values_list("pk", flat=True)
        else:
            ids = MemberProfile.objects.filter(membership__user=instance).values_list("pk", flat=True)
        for pk in ids:
            invalidate_profile(pk)

    for model in (MemberProfile, MemberProject, ProfileTimelineEntry, PublicHandle,
                  MakerspaceMembership, Makerspace, get_user_model()):
        for signal in (post_save, post_delete):
            signal.connect(changed, sender=model, weak=False,
                           dispatch_uid=f"public-profile:{signal}:{model._meta.label}")
