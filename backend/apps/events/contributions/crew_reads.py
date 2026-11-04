"""Crew read models: the staff roster, the catering summary, the public section, a member's own row.

Dietary needs are sensitive (#28): the catering summary returns counts per need, never
who has them. The public section lists only approved crew who opted in AND hold a live
public profile in the event's space (#25); it shows their handle and display name only.
"""
from collections import Counter

from .models_crew import EventCrewMember


def project_staff(crew):
    registration = crew.registration
    return {"id": crew.pk, "version": crew.version, "member_id": crew.member_id,
            "name": crew.member.display_name or crew.member.username, "crew_role": crew.crew_role,
            "state": crew.state, "origin": crew.origin, "show_publicly": crew.show_publicly,
            "registration_id": registration.pk if registration else None,
            "has_place": bool(registration and registration.is_crew and registration.status in ("registered", "attended")),
            "created_at": crew.created_at, "decided_at": crew.decided_at}


def project_own(crew):
    return {"id": crew.pk, "version": crew.version, "crew_role": crew.crew_role, "state": crew.state,
            "show_publicly": crew.show_publicly, "registration_id": crew.registration_id}


def roster(event):
    return EventCrewMember.objects.filter(event=event).select_related("member", "registration").order_by("state", "pk")


def catering(event):
    approved = EventCrewMember.objects.filter(event=event, state="approved")
    needs = Counter()
    for crew in approved:
        for need in (part.strip().casefold() for part in (crew.dietary or "").split(",")):
            if need:
                needs[need[:60]] += 1
    return {"approved": approved.count(), "with_needs": sum(1 for crew in approved if (crew.dietary or "").strip()),
            "needs": [{"label": label, "count": count} for label, count in sorted(needs.items())]}


def public_crew(event):
    from apps.makerspaces.models_profiles import PublicHandle
    from apps.makerspaces.profile_services import display_name_for
    from apps.makerspaces.public_profile_access import profile_is_public
    from apps.events.models_participation import EventParticipationSettings
    if not EventParticipationSettings.for_event(event).crew_public_section:
        return []
    rows = EventCrewMember.objects.filter(event=event, state="approved", show_publicly=True).order_by("pk")
    handles = {claim.user_id: claim for claim in PublicHandle.objects.filter(
        user_id__in=rows.values("member_id"), profile__membership__makerspace_id=event.makerspace_id,
    ).select_related("profile__membership__user", "profile__membership__makerspace")}
    result = []
    for crew in rows:
        claim = handles.get(crew.member_id)
        if claim is not None and profile_is_public(claim.profile):
            result.append({"handle": claim.handle, "display_name": display_name_for(claim.profile.membership),
                           "crew_role": crew.crew_role})
    return result


def crew_flags(registration_ids):
    """Registration id -> crew role, for badges, tickets and event cards (L3 reads the flag)."""
    rows = EventCrewMember.objects.filter(state="approved").filter(registration_id__in=registration_ids)
    return {row.registration_id: row.crew_role or "Crew" for row in rows}
