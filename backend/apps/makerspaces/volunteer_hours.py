"""Decision 223 (k), lane L3b: logging and approving volunteer hours.

Members log their own hours (pending); staff approve or reject them, or log hours for a member themselves
(staff-logged hours are approved at once: the logger is the approver, audited either way). Verified event
shift hours arrive through the events adapter (`events/volunteer_hours_adapter.py`) as PENDING entries with
their source row recorded, so one shift can never be counted twice. Approval converts approved minutes into
credits under the space's policy (`volunteer_credit.convert_available_minutes`); it never touches a price.
"""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.makerspaces.community_policy import CommunityError, volunteer_on
from apps.makerspaces.models import MakerspaceMembership, VolunteerHourEntry


def _require_member(makerspace, member):
    if not MakerspaceMembership.objects.filter(makerspace=makerspace, user=member, status="active").exists():
        raise CommunityError("membership_required", "Volunteer hours belong to an active member of this space.")


def _check(minutes, worked_on, makerspace=None):
    if not isinstance(minutes, int) or not 0 < minutes <= 1440:
        raise ValidationError({"minutes": "Give between 1 and 1440 minutes."})
    from apps.makerspaces.local_time import to_local
    today = to_local(makerspace, timezone.now()).date() if makerspace is not None else timezone.localdate()
    if worked_on > today:  # m13: the space's local day
        raise ValidationError({"worked_on": "Hours cannot be logged for a future day."})


def log_hours(actor, makerspace, member, *, minutes, worked_on, description="", by_staff=False):
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    _check(minutes, worked_on, makerspace)
    _require_member(makerspace, member)
    assert_write_allowed(makerspace.pk)
    now = timezone.now()
    with transaction.atomic():
        entry = VolunteerHourEntry.objects.create(
            makerspace=makerspace, member=member, minutes=minutes, worked_on=worked_on,
            description=(description or "").strip()[:200], submitted_by=actor,
            status=(VolunteerHourEntry.Status.APPROVED if by_staff else VolunteerHourEntry.Status.PENDING),
            reviewed_by=actor if by_staff else None, reviewed_at=now if by_staff else None)
        audit.record(actor, "membership.volunteer_hours_logged", makerspace=makerspace, target=entry,
                     meta={"minutes": minutes, "by_staff": bool(by_staff)})
        if by_staff:
            _convert(actor, makerspace, member)
    return entry


def review_entry(actor, entry, *, approve, note=""):
    """Staff decision on one pending entry. Only a pending entry can be decided, once."""
    with transaction.atomic():
        row = VolunteerHourEntry.objects.select_for_update().select_related("makerspace").get(pk=entry.pk)
        if row.status != VolunteerHourEntry.Status.PENDING:
            raise CommunityError("entry_not_pending", "This entry has already been decided.", 409)
        row.status = VolunteerHourEntry.Status.APPROVED if approve else VolunteerHourEntry.Status.REJECTED
        row.reviewed_by, row.reviewed_at, row.review_note = actor, timezone.now(), (note or "").strip()[:200]
        row.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note"])
        audit.record(actor, "membership.volunteer_hours_decided", makerspace=row.makerspace, target=row,
                     meta={"approved": bool(approve), "minutes": row.minutes})
        if approve:
            _convert(actor, row.makerspace, row.member)
    return row


def _convert(actor, makerspace, member):
    if volunteer_on(makerspace):
        from apps.makerspaces.volunteer_credit import convert_available_minutes
        convert_available_minutes(actor, makerspace, member)


def approved_minutes(makerspace, member):
    from django.db.models import Sum
    return VolunteerHourEntry.objects.filter(
        makerspace=makerspace, member=member, status=VolunteerHourEntry.Status.APPROVED,
    ).aggregate(total=Sum("minutes"))["total"] or 0
