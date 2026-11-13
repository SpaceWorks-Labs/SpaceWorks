"""Typed leave remarks ("how did it go?") from staff or the booking owner, with issue opening.

One departure per booking: the first record wins and later attempts are refused, so the
history cannot be rewritten by a second checkout. Anything but "all good" requires a remark
and opens one `BookingIssue` that surfaces on the bookings Issues list and dashboard.
"""

from django.utils.translation import gettext
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.audit import services as audit

from . import booking_authority
from .exceptions import BookingInvalidTransition
from .models_departure import BookingDepartureEvent, BookingIssue, DepartureOutcome, DepartureSource
from .services_bookings import _locked_booking, _refresh

MAX_REMARK = 2000
EARLIEST_BEFORE_START = timedelta(minutes=30)
MEMBER_GRACE_AFTER_END = timedelta(hours=48)


def clean_departure(outcome, remark):
    if outcome not in DepartureOutcome.values:
        raise serializers.ValidationError({"outcome": gettext("Choose how the booking went.")})
    remark = (remark or "").strip()
    if outcome != DepartureOutcome.ALL_GOOD and not remark:
        raise serializers.ValidationError({"remark": gettext("Describe what was wrong so staff can follow up.")})
    if len(remark) > MAX_REMARK:
        raise serializers.ValidationError({"remark": gettext('Keep the remark under {MAX_REMARK} characters.').format(MAX_REMARK=MAX_REMARK)})
    return outcome, remark


def can_depart(booking, *, now, source):
    if booking.departed_at is not None or booking.status not in ("confirmed", "completed"):
        return False
    if now < booking.starts_at - EARLIEST_BEFORE_START:
        return False
    return source == DepartureSource.STAFF or now <= booking.ends_at + MEMBER_GRACE_AFTER_END


def staff_may_record(actor, space):
    return (booking_authority.can(actor, space, "check_in")
            or booking_authority.can(actor, space, "manage_reservations"))


@transaction.atomic
def record_departure(booking, *, actor, outcome, remark="", source=DepartureSource.STAFF):
    outcome, remark = clean_departure(outcome, remark)
    space, locked = _locked_booking(booking)
    locked.space = space
    if source == DepartureSource.STAFF:
        from rest_framework.exceptions import PermissionDenied
        booking_authority.require(actor, space, "view")
        if not staff_may_record(actor, space):
            raise PermissionDenied()
    else:
        from apps.makerspaces.guards import require_module_locked
        require_module_locked(space.makerspace, "bookings")
        if locked.member_id is None or locked.member_id != getattr(actor, "pk", None):
            raise BookingInvalidTransition("Only the booking owner can check out.")
    now = timezone.now()
    if locked.departed_at is not None:
        raise BookingInvalidTransition("A departure is already recorded for this booking.")
    if not can_depart(locked, now=now, source=source):
        raise BookingInvalidTransition("Check-out is open from 30 minutes before the start of a confirmed booking.")
    event = BookingDepartureEvent.objects.create(
        makerspace=space.makerspace, booking=locked, actor=actor, outcome=outcome, remark=remark, source=source,
    )
    locked.departed_at = now
    locked.save(update_fields=["departed_at"])
    issue = None
    if outcome != DepartureOutcome.ALL_GOOD:
        issue = BookingIssue.objects.create(makerspace=space.makerspace, booking=locked, departure=event, outcome=outcome)
    # Remark text is scoped PII on the event row; the append-only audit carries facts only.
    audit.record(actor, "booking.departure_recorded", makerspace=space.makerspace, target=locked, meta={
        "booking_id": locked.pk, "outcome": outcome, "source": source,
        "has_remark": bool(remark), "issue_id": issue.pk if issue else None,
    })
    return _refresh(locked)


@transaction.atomic
def resolve_issue(issue, *, actor, note=""):
    locked = BookingIssue.objects.select_for_update().select_related("booking__space__makerspace").get(pk=issue.pk)
    booking_authority.require(actor, locked.booking.space, "manage_reservations")
    note = (note or "").strip()
    if len(note) > 500:
        raise serializers.ValidationError({"note": gettext("Keep the note under 500 characters.")})
    if locked.resolved_at is not None:
        return locked
    locked.resolved_at, locked.resolved_by, locked.resolution_note = timezone.now(), actor, note
    locked.save(update_fields=["resolved_at", "resolved_by", "resolution_note"])
    audit.record(actor, "booking.issue_resolved", makerspace=locked.makerspace, target=locked.booking, meta={
        "issue_id": locked.pk, "booking_id": locked.booking_id, "outcome": locked.outcome,
    })
    return locked
