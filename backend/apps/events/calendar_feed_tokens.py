"""Issue, rotate, revoke and resolve a person's shift or combined calendar link (release 2 L18).

Same bearer rules as the existing member and booking feeds: a 256-bit token shown once,
only its SHA-256 digest stored, a rotation or revocation kills the old link, and every change
is audited (`calendar_feed.created|rotated|revoked`, never the token).
"""

import hmac
import re
import secrets

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit

from .models import PersonalCalendarFeed
from .services_calendar_feeds import token_digest

TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{43}")


def feed_state(space, user, kind):
    row = PersonalCalendarFeed.objects.filter(makerspace=space, user=user, kind=kind,
                                              revoked_at__isnull=True).first()
    return {"enabled": row is not None, "token_hint": row.token_hint if row else None,
            "created_at": row.created_at if row else None, "rotated_at": row.rotated_at if row else None}


@transaction.atomic
def issue_or_rotate(space, user, kind):
    """Returns `(row, raw_token)`; the raw token is never stored or logged."""
    from apps.accounts.models import User

    User.objects.select_for_update().get(pk=user.pk)  # serialize issue and rotation per person
    raw = secrets.token_urlsafe(32)
    row = PersonalCalendarFeed.objects.select_for_update().filter(makerspace=space, user=user, kind=kind).first()
    if row is None:
        row = PersonalCalendarFeed.objects.create(makerspace=space, user=user, kind=kind,
                                                  token_digest=token_digest(raw), token_hint=raw[-8:])
        audit.record(user, "calendar_feed.created", makerspace=space, target=row,
                     meta={"kind": kind})
        return row, raw
    row.token_digest, row.token_hint = token_digest(raw), raw[-8:]
    row.rotated_at, row.revoked_at = timezone.now(), None
    row.save(update_fields=["token_digest", "token_hint", "rotated_at", "revoked_at"])
    audit.record(user, "calendar_feed.rotated", makerspace=space, target=row, meta={"kind": kind})
    return row, raw


@transaction.atomic
def revoke(space, user, kind):
    row = PersonalCalendarFeed.objects.select_for_update().filter(
        makerspace=space, user=user, kind=kind, revoked_at__isnull=True).first()
    if row is None:
        return False
    row.revoked_at = timezone.now()
    row.save(update_fields=["revoked_at"])
    audit.record(user, "calendar_feed.revoked", makerspace=space, target=row, meta={"kind": kind})
    return True


def resolve(space, raw, kind):
    """The live feed row for this token in this space, else None (no oracle: callers answer 404)."""
    if not TOKEN_RE.fullmatch(raw or ""):
        return None
    digest = token_digest(raw)
    row = PersonalCalendarFeed.objects.select_related("user").filter(
        makerspace=space, kind=kind, token_digest=digest, revoked_at__isnull=True).first()
    if row is None or not hmac.compare_digest(bytes(row.token_digest), digest):
        return None
    return row
