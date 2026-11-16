"""Decision 223 (k), lane L3b: verified event-shift hours offered to the membership volunteer credit.

The events side of the adapter: core (`makerspaces`) never imports events, so this module reads the
verified contribution hours and writes PENDING `VolunteerHourEntry` rows that carry the source row id. Staff
still approve each entry in the volunteer queue; importing twice is a no-op (the source is unique per space).
Only members with an active membership at the host space are imported.
"""
from django.db import IntegrityError, transaction

from apps.audit import services as audit
from apps.makerspaces.community_policy import volunteer_on
from apps.makerspaces.models import MakerspaceMembership, VolunteerHourEntry
from apps.makerspaces.platform import feature_enabled, module_enabled


def import_verified_hours(actor, makerspace):
    """Create pending entries for verified hours not yet imported. Returns how many were created."""
    if not (volunteer_on(makerspace) and module_enabled(makerspace, "events")
            and feature_enabled(makerspace, "events.volunteering")):
        return 0
    from apps.events.contributions.models_shifts import EventContributionHours
    done = VolunteerHourEntry.objects.filter(
        makerspace=makerspace, source=VolunteerHourEntry.Source.EVENT_SHIFT).values("source_ref")
    rows = (EventContributionHours.objects.filter(
        makerspace=makerspace, state__in=("verified", "adjusted"), minutes__gt=0)
        .exclude(pk__in=done).select_related("signup__member", "signup__shift"))
    members = set(MakerspaceMembership.objects.filter(makerspace=makerspace, status="active")
                  .values_list("user_id", flat=True))
    created = 0
    with transaction.atomic():
        # Serialise concurrent imports on the space row; the unique source constraint below is the
        # backstop, so a lost race skips the row instead of surfacing an IntegrityError as a 500.
        type(makerspace).objects.select_for_update().filter(pk=makerspace.pk).first()
        for hours in rows[:500]:
            signup = hours.signup
            if signup.member_id not in members:
                continue
            try:
                with transaction.atomic():
                    VolunteerHourEntry.objects.create(
                        makerspace=makerspace, member=signup.member, minutes=min(hours.minutes, 1440),
                        worked_on=signup.shift.starts_at.date(), description=signup.shift.task[:200],
                        source=VolunteerHourEntry.Source.EVENT_SHIFT, source_ref=hours.pk, submitted_by=actor)
            except IntegrityError:
                continue  # already imported by a concurrent run
            created += 1
        if created:
            audit.record(actor, "membership.volunteer_hours_imported", makerspace=makerspace,
                         meta={"count": created})
    return created
