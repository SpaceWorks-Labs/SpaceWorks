"""Series allowlist (parity E-B5, B12/B14): an email that may register for every occurrence of a series.

A series entry is an `EventInvite` bound to the series instead of one event. It holds an email digest
only (never a clear email or a code), is never consumed, and is checked live at admission, so an
occurrence added later is covered at once and a revoked or expired entry stops admitting at once. Event
invites keep their own counted, one-event rules; this module never touches them.
"""
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework import serializers

from apps.audit import services as audit
from apps.makerspaces.guards import require_module_locked
from apps.makerspaces.platform import feature_enabled

from . import event_authority
from .event_permissions import MANAGE_INVITATIONS
from .feature_gates import require_feature
from .invites import code_digest
from .models import EventInvite, EventSeries

FEATURE = "events.series_invites"
MAX_BATCH = 200


def _locked_series(series_id):
    return EventSeries.objects.select_for_update(of=("self",)).select_related("makerspace").get(pk=series_id)


def _require(actor, series):
    event_authority.require(actor, series, MANAGE_INVITATIONS)
    series.makerspace = require_module_locked(series.makerspace, "events")
    require_feature(series, FEATURE)


def _live(rows, now):
    return rows.filter(revoked_at__isnull=True).exclude(expires_at__lte=now)


@transaction.atomic
def add(series, *, actor, emails, expires_at=None):
    """Allow each email on the series. Returns (rows, skipped) where skipped were already live."""
    from apps.managed_hosting.extra_quotas import check_extra_quota
    payload = serializers.ListField(child=serializers.EmailField(), min_length=1,
                                    max_length=MAX_BATCH).run_validation(emails)
    payload = list(dict.fromkeys(email.strip().lower() for email in payload))
    series = _locked_series(series.pk)
    _require(actor, series)
    now = timezone.now()
    if expires_at and expires_at <= now:
        raise serializers.ValidationError({"expires_at": gettext("Use a future expiry.")})
    live = {row.email_digest for row in _live(EventInvite.objects.filter(series=series), now)}
    created, skipped = [], 0
    for address in payload:
        digest = code_digest(address, "email")
        if digest in live:
            skipped += 1
            continue
        check_extra_quota(series.makerspace, "series_invites")
        created.append(EventInvite.objects.create(
            series=series, makerspace=series.makerspace, email_digest=digest, expires_at=expires_at))
    audit.record(actor, "event.series_invite.created", makerspace=series.makerspace, target=series,
                 meta={"series_id": series.pk, "count": len(created), "skipped": skipped})
    return created, skipped


@transaction.atomic
def revoke(invite, *, actor):
    series = _locked_series(invite.series_id)
    _require(actor, series)
    locked = EventInvite.objects.select_for_update().get(pk=invite.pk, series=series)
    if not locked.revoked_at:
        locked.revoked_at = timezone.now()
        locked.save(update_fields=["revoked_at"])
        audit.record(actor, "event.series_invite.revoked", makerspace=series.makerspace, target=series,
                     meta={"series_id": series.pk, "invite_id": locked.pk})
    return locked


def allowlisted_locked(event, member):
    """The live series entry that admits this verified member to one occurrence, or None.

    Not consumed: the allowlist is a standing permission for the series. Off means removed everywhere.
    """
    if (not event.series_id or member is None or not member.email or not member.email_verified_at
            or not feature_enabled(event.makerspace, FEATURE)):
        return None
    rows = _live(EventInvite.objects.filter(series_id=event.series_id, makerspace=event.makerspace,
                                            email_digest=code_digest(member.email, "email")), timezone.now())
    return rows.order_by("pk").first()
