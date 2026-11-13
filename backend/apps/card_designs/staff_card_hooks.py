"""Staff-card lifecycle hooks called from the staff role services (O-B4 part 2).

Each runs in a SAVEPOINT and swallows every error: a card problem is logged and audited, and never undoes or
blocks the staff change that triggered it (roles granted/changed, row revoked, account restricted).
"""
import logging

from django.db import transaction

from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.platform import feature_enabled

from .models_staff_cards import StaffCard
from .staff_card_roles import role_slugs
from .switches import STAFF_CARDS_AUTO, staff_cards_on

logger = logging.getLogger(__name__)


def after_roles_changed(actor, membership):
    """Roles written for a membership: auto-issue on a fresh grant, reissue (same number) when the set changed."""
    if membership is None or membership.track != MakerspaceMembership.Track.STAFF:
        return None
    try:
        with transaction.atomic():
            space = membership.makerspace
            if not staff_cards_on(space):
                return None
            from . import staff_card_services as services
            card = services.live_card(membership)
            if card is None:
                return services.auto_issue(membership) if feature_enabled(space, STAFF_CARDS_AUTO) else None
            if sorted(card.roles or []) != sorted(role_slugs(membership)):
                return services.reissue_locked(actor, card, reason="roles_changed")
    except Exception:
        logger.exception("staff_card_after_roles_changed_failed",
                         extra={"membership_id": getattr(membership, "pk", None)})
    return None


def after_access_ended(actor, membership, *, reason="staff_access_ended"):
    """A staff row was revoked (or its account disabled): revoke its live card(s). Runs whether or not the switch is on."""
    try:
        with transaction.atomic():
            from . import staff_card_services as services
            for card in StaffCard.objects.filter(membership=membership, revoked_at__isnull=True):
                services.revoke_locked(actor, card, reason=reason)
    except Exception:
        logger.exception("staff_card_revoke_failed", extra={"membership_id": getattr(membership, "pk", None)})


def after_user_access_changed(actor, user):
    """An account was restricted or suspended: every live staff card of the person is revoked (audited)."""
    if user.access_status == "active":
        return
    try:
        with transaction.atomic():
            from . import staff_card_services as services
            for card in StaffCard.objects.filter(membership__user=user, revoked_at__isnull=True):
                services.revoke_locked(actor, card, reason="account_restricted")
    except Exception:
        logger.exception("staff_card_account_revoke_failed", extra={"user_id": getattr(user, "pk", None)})
