"""Decision 248: the roster's remaining filters -- plan, staff, waiver-needed, verified, minor and volunteer.

Each is a plain SQL predicate over the already-scoped roster queryset (never a per-row loop), so the page count
stays honest. A value other than the documented ones is ignored, like the roster's other optional filters.
"""

from django.db.models import Exists, OuterRef, Q

TRUE, FALSE = "true", "false"


def _flag(params, key):
    value = str(params.get(key, "")).lower()
    return value if value in (TRUE, FALSE) else None


def _apply(queryset, predicate, wanted):
    return queryset.filter(predicate) if wanted == TRUE else queryset.exclude(predicate)


def apply_roster_filters(queryset, params, makerspace):
    from apps.makerspaces.models import MakerspaceMembership, MembershipTerm, MinorProfile, VolunteerHourEntry
    from apps.makerspaces.waiver_state import active_waiver_for

    if str(params.get("plan", "")).isdigit():
        queryset = queryset.filter(Exists(MembershipTerm.objects.filter(
            membership=OuterRef("pk"), plan_id=int(params["plan"]), status="active")))
    if wanted := _flag(params, "staff"):
        staff = Exists(MakerspaceMembership.staff_tracks.filter(
            makerspace=makerspace, user=OuterRef("user"), status="active"))
        queryset = _apply(queryset, staff, wanted)
    if wanted := _flag(params, "verified"):
        queryset = _apply(queryset, Q(verified_at__isnull=False), wanted)
    if wanted := _flag(params, "minor"):
        minor = Exists(MinorProfile.objects.filter(makerspace=makerspace, user=OuterRef("user"), cleared_at__isnull=True))
        queryset = _apply(queryset, minor, wanted)
    if wanted := _flag(params, "volunteer"):
        volunteer = Exists(VolunteerHourEntry.objects.filter(
            makerspace=makerspace, member=OuterRef("user"), status="approved"))
        queryset = _apply(queryset, volunteer, wanted)
    if _flag(params, "waiver_needed") == TRUE:
        waiver = active_waiver_for(makerspace.pk)
        if waiver is None:
            return queryset.none()
        current = (Q(accepted_waiver_id=waiver.pk, waiver_version_accepted=waiver.version)
                   | Q(witnessed_waiver_id=waiver.pk, witnessed_waiver_version=waiver.version))
        queryset = queryset.exclude(current)
    return queryset
