"""Public check-link tokens: 43-char base64url (256-bit), one live token per card.

A token is never the desk QR payload (32 hex) and never appears in logs, audit meta,
staff QR listings, exports or wallet passes (#71).
"""
import re
import secrets

from django.conf import settings
from django.utils import timezone

from .models import CardVerifyToken

SHAPE = re.compile(r"^[A-Za-z0-9_-]{43}$")


def live(kind, card):
    return CardVerifyToken.objects.filter(**{kind: card}, retired_at__isnull=True).first()


def mint(kind, card):
    current = live(kind, card)
    if current is not None:
        return current
    return CardVerifyToken.objects.create(makerspace_id=card.makerspace_id, token=secrets.token_urlsafe(32),
                                          **{kind: card})


def retire(kind, card, reason):
    CardVerifyToken.objects.filter(**{kind: card}, retired_at__isnull=True).update(
        retired_at=timezone.now(), retired_reason=reason)


def rotate(kind, card, reason=CardVerifyToken.Retired.ROTATED):
    retire(kind, card, reason)
    return mint(kind, card)


def url(token):
    base = (getattr(settings, "PUBLIC_APP_BASE_URL", "") or "http://localhost:5000").rstrip("/")
    return f"{base}/verify/c/{token}" if token else ""


def short_url(token):
    """The printed form: scheme-less, so it fits on a CR80 back in 6 pt."""
    return re.sub(r"^https?://", "", url(token))
