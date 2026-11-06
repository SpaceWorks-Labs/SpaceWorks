"""Invites for imported or staff-added entries, and linking on acceptance (#128 C-13).

An entry links to an account ONLY when the person opens their emailed invite while
signed in with a VERIFIED email equal to the entry's email. There is no silent linking
on sign-in and no account is ever created here. The invite secret is mailed once and
only its digest is stored; the mail body is never persisted (it carries the secret).
"""
from django.utils.translation import gettext
import hashlib
import hmac
import logging
import secrets

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit import services as audit

from .models import IdProgrammeCard

logger = logging.getLogger(__name__)


def _digest(token):
    return hashlib.sha256(("id-programme-invite:" + token).encode()).hexdigest()


def send_invites(card_ids):
    from apps.integrations.dispatch_outbox import dispatch_email
    base = (getattr(settings, "PUBLIC_APP_BASE_URL", "") or "").rstrip("/")
    for card in IdProgrammeCard.objects.filter(pk__in=card_ids, user__isnull=True).select_related(
            "programme__organization", "makerspace"):
        if not card.email:
            continue
        token = secrets.token_urlsafe(32)
        IdProgrammeCard.objects.filter(pk=card.pk).update(invite_digest=_digest(token))
        programme = card.programme
        link = f"{base}/member/cards/accept?invite={token}&card={card.pk}"
        body = (f"Hello {card.name},\n\n{programme.organization.name} added you to “{programme.name}”.\n"
                f"Sign in (or create your account) with this email address and open:\n{link}\n\n"
                "Your card appears under My cards once you accept.")
        try:
            dispatch_email(to_email=card.email, subject=gettext('Your {name} card from {name2}').format(name=programme.name, name2=programme.organization.name),
                           text_body=body, makerspace=card.makerspace, stream="membership", event="programme_invite",
                           audience="requester", persist_body=False, sync=True)
        except Exception:
            logger.warning("id_programme_invite_failed", extra={"card_id": card.pk})


@transaction.atomic
def accept(user, card_id, token):
    from apps.card_designs.switches import programmes_on
    card = IdProgrammeCard.objects.select_for_update().filter(pk=card_id, user__isnull=True).first()
    if (card is None or not card.invite_digest or not isinstance(token, str)
            or not hmac.compare_digest(card.invite_digest, _digest(token)) or not programmes_on(card.makerspace)):
        raise NotFound()
    if not user.email_verified_at:
        raise ValidationError({"detail": gettext("Verify your email address first, then open the invite again.")})
    if (user.email or "").strip().lower() != (card.email or "").strip().lower():
        raise ValidationError({"detail": gettext("Sign in with the email address the invite was sent to.")})
    if IdProgrammeCard.objects.filter(programme=card.programme, user=user).exists():
        raise ValidationError({"detail": gettext("You already hold a card in this programme.")})
    card.user, card.invite_digest = user, ""
    card.save(update_fields=["user", "invite_digest", "updated_at"])
    audit.record(user, "id_programme.card_linked", makerspace=card.makerspace, target=card,
                 meta={"card_id": card.pk, "programme_id": card.programme_id})
    return card

