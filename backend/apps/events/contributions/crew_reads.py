"""Crew read models: the staff roster, the catering summary, the public section, a member's own row.

Dietary needs are sensitive (#28): the catering summary returns counts per need, never
who has them. The public section lists only approved crew who opted in AND hold a live
public profile in the event's space (#25); it shows their handle and display name only.
"""
from collections import Counter

from django.utils.translation import gettext

from .models_crew import EventCrewMember


def _kinds_on(event):
    from apps.makerspaces.platform import feature_enabled
    return feature_enabled(event.makerspace, "events.crew_kinds")


def kind_label(kind):
    """The translated name of a crew kind, or "" for none/unknown."""
    return gettext(EventCrewMember.Kind(kind).label) if kind in EventCrewMember.Kind.values else ""


def project_staff(crew):
    registration = crew.registration
    return {"id": crew.pk, "version": crew.version, "member_id": crew.member_id,
            "name": crew.member.display_name or crew.member.username, "crew_role": crew.crew_role,
            "state": crew.state, "origin": crew.origin, "show_publicly": crew.show_publicly,
            "kind": crew.kind, "position": crew.position, "staff_hidden": crew.staff_hidden,
            "registration_id": registration.pk if registration else None,
            "has_place": bool(registration and registration.is_crew and registration.status in ("registered", "attended")),
            "created_at": crew.created_at, "decided_at": crew.decided_at}


def project_own(crew):
    return {"id": crew.pk, "version": crew.version, "crew_role": crew.crew_role, "state": crew.state,
            "show_publicly": crew.show_publicly, "registration_id": crew.registration_id}


def roster(event, kind=None):
    """The staff roster in staff order; `kind` filters only while `events.crew_kinds` is on."""
    rows = EventCrewMember.objects.filter(event=event).select_related("member", "registration")
    if kind and _kinds_on(event):
        rows = rows.filter(kind=kind)
    return rows.order_by("state", "position", "pk")


def catering(event):
    approved = EventCrewMember.objects.filter(event=event, state="approved")
    needs = Counter()
    for crew in approved:
        for need in (part.strip().casefold() for part in (crew.dietary or "").split(",")):
            if need:
                needs[need[:60]] += 1
    return {"approved": approved.count(), "with_needs": sum(1 for crew in approved if (crew.dietary or "").strip()),
            "needs": [{"label": label, "count": count} for label, count in sorted(needs.items())]}


def public_crew(event, *, require_switch=True):
    from apps.makerspaces.models_profiles import PublicHandle
    from apps.makerspaces.account_profile import display_name_for_user
    from apps.makerspaces.account_profile_spaces import listed_space_ids
    from apps.makerspaces.public_profile_access import account_is_open_web
    from apps.events.models_participation import EventParticipationSettings
    # The per-event block reads the event's switch; a Pages section is its own opt-in (#165 auto).
    if require_switch and not EventParticipationSettings.for_event(event).crew_public_section:
        return []
    rows = EventCrewMember.objects.filter(event=event, state="approved", show_publicly=True,
                                          staff_hidden=False).order_by("position", "pk")
    handles = {claim.user_id: claim for claim in PublicHandle.objects.filter(
        user_id__in=rows.values("member_id")).select_related("user")}
    result, kinds = [], _kinds_on(event)
    for crew in rows:
        claim = handles.get(crew.member_id)
        # Open-web audience: the account profile is open AND the person is an active member of this space.
        if (claim is not None and account_is_open_web(claim.user)
                and event.makerspace_id in listed_space_ids(claim.user)):
            result.append({"handle": claim.handle, "display_name": display_name_for_user(claim.user),
                           "crew_role": crew.crew_role, "kind": crew.kind if kinds else None})
    return result


def crew_flags(registration_ids):
    """Registration id -> crew role, for badges, tickets and event cards (L3 reads the flag)."""
    rows = EventCrewMember.objects.filter(state="approved").filter(registration_id__in=registration_ids)
    return {row.registration_id: row.crew_role or "Crew" for row in rows}


def crew_label(crew_role, kind=None):
    """The chip text: "Kind - role" with a kind, "Mentor" for a mentor crew ticket, else the label, else "Crew"."""
    role = (crew_role or "").strip()
    name = kind_label(kind)
    if name:
        return name if not role or role.casefold() in (name.casefold(), kind) else f"{name} \u00b7 {role[:60]}"
    if role.casefold() == "mentor":
        return "Mentor"
    return role[:60] or "Crew"


def crew_labels(event, registration_ids):
    """Registration id -> chip text for badges, tickets and event cards; empty while `events.crew` is off."""
    from apps.makerspaces.platform import feature_enabled
    if not registration_ids or not feature_enabled(event.makerspace, "events.crew"):
        return {}
    rows = EventCrewMember.objects.filter(event=event, state="approved", registration_id__in=list(registration_ids))
    kinds = _kinds_on(event)
    return {row.registration_id: crew_label(row.crew_role, row.kind if kinds else None) for row in rows}


def crew_kinds(event, registration_ids):
    """Registration id -> crew kind, for approved crew that have one; empty while the crew or kinds switch is off."""
    from apps.makerspaces.platform import feature_enabled
    if not registration_ids or not feature_enabled(event.makerspace, "events.crew") or not _kinds_on(event):
        return {}
    rows = EventCrewMember.objects.filter(event=event, state="approved", registration_id__in=list(registration_ids),
                                          kind__isnull=False)
    return {row.registration_id: row.kind for row in rows}


def crew_kind_for(event, registration_id):
    """The crew kind of one registration ("" when none); the badge role resolver reads it (E-B2)."""
    return crew_kinds(event, [registration_id]).get(registration_id, "")
