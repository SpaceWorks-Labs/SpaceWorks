"""A primary-title change reissues the member's live card (O-B4, parity C7).

Same number, new desk QR and verify token (the old printed card verifies as "a newer card was issued"),
wallet pass update queued, audited as `member_card.reissued` with reason `title_changed`. Runs inside the
title-assignment transaction, so the title and the card change together. Off unless the space turned on
`membership.title_card_reissue`; never blocks the title change itself.
"""
import logging

from django.db import transaction

from .switches import TITLE_REISSUE

logger = logging.getLogger(__name__)


def after_title_change(actor, membership, before):
    from apps.makerspaces.member_card_services import reissue_locked
    from apps.makerspaces.membership_titles import primary_title
    from apps.makerspaces.models import MemberCard
    from apps.makerspaces.platform import feature_enabled, module_enabled
    space = membership.makerspace
    after = primary_title(membership)
    if (before.pk if before else None) == (after.pk if after else None):
        return []
    if not (module_enabled(space, "membership") and feature_enabled(space, TITLE_REISSUE)):
        return []
    done = []
    for card in MemberCard.objects.filter(membership=membership, revoked_at__isnull=True):
        try:
            with transaction.atomic():  # a savepoint: a failed reissue leaves the title assignment intact
                done.append(reissue_locked(actor, card, reason="title_changed"))
        except Exception:  # a card problem must never undo the title assignment
            logger.exception("title_card_reissue_failed", extra={"card_id": card.pk})
    return done
