"""The only writer of the event crew and of crew places (lane L21a, X44, #128 C-36).

A crew place is a registration flagged `is_crew`: free (no charge is ever raised), outside
capacity, never part of an order and never on a team. A person who already holds a
participant registration keeps it as it is; their crew role still shows on their badge.
Being on the crew grants NO event staff authority.
"""
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.audit import services as audit
from apps.makerspaces.platform import feature_enabled

from apps.events.hackathons.admission_errors import fail
from apps.events.services_write_boundary import event_write
from .models_crew import LIVE, EventCrewMember

FEATURE = "events.crew"
LIVE_REGISTRATION = ("registered", "attended", "pending_approval", "waitlisted")


def require_feature(event):
    if not feature_enabled(event.makerspace, FEATURE):
        fail("not_found", "Not found.", status=404)


def _open(event):
    if event.status != "published" or timezone.now() >= event.ends_at:
        fail("event_closed", "This event no longer takes crew.")


def place_locked(event, crew, actor):
    """Give an approved crew member their free place, outside capacity and uncharged."""
    from apps.events.models import EventRegistration
    member = crew.member
    existing = EventRegistration.objects.select_for_update().filter(event=event, member=member).first()
    if existing is not None and existing.status in LIVE_REGISTRATION:
        return None  # a participant keeps their own registration; it is not converted
    if existing is not None:
        row = existing  # one registration per email and event: reuse a cancelled or declined one
    else:
        row = EventRegistration(event=event, member=member, registered_via_makerspace=event.makerspace,
                                payment_via_makerspace=event.makerspace)
    row.name = member.display_name or member.username
    row.email, row.phone = member.email or "", member.phone or ""
    row.status, row.is_crew, row.quoted_amount, row.discount_amount = "registered", True, 0, 0
    row.ticket_type = row.promo_code = None
    row.cancelled_at, row.status_before_cancel = None, ""
    if existing is not None:
        row.version += 1
    row.save()
    from apps.events.services_calendar import calendar_registration_changed
    calendar_registration_changed(row)
    crew.registration = row
    audit.record(actor, "event.crew.place_created", makerspace=event.makerspace, target=crew,
                 meta={"event_id": event.pk, "crew_id": crew.pk, "state": crew.state, "registration_id": row.pk})
    return row


def release_locked(crew, actor):
    from apps.events.services_registration_state import cancel_registration
    registration = crew.registration
    if registration is not None and registration.is_crew and registration.status == "registered":
        cancel_registration(registration, actor=None)
        audit.record(actor, "event.crew.place_released", makerspace=crew.event.makerspace, target=crew,
                     meta={"event_id": crew.event_id, "crew_id": crew.pk, "state": crew.state,
                           "registration_id": registration.pk})


@event_write
def signup(event, *, actor, crew_role="", answers="{}", dietary="", show_publicly=False):
    from apps.events.hackathons.admission_transactions import require_member
    from apps.events.models_participation import EventParticipationSettings
    require_feature(event)
    require_member(actor)
    settings = EventParticipationSettings.for_event(event)
    if not settings.crew_signup_open:
        fail("not_found", "Not found.", status=404)
    _open(event)
    if EventCrewMember.objects.filter(event=event, member=actor, state__in=LIVE).exists():
        fail("crew_exists", "You already signed up for this crew.")
    crew = EventCrewMember.objects.create(makerspace=event.makerspace, event=event, member=actor, crew_role=crew_role,
                                          answers=answers, dietary=dietary, show_publicly=show_publicly)
    audit.record(actor, "event.crew.signed_up", makerspace=event.makerspace, target=crew,
                 meta={"event_id": event.pk, "crew_id": crew.pk, "state": crew.state})
    if not settings.crew_approval_required:
        _approve_locked(event, crew, actor, reason="auto_approved")
    return crew


def _approve_locked(event, crew, actor, *, reason):
    crew.state, crew.decided_by, crew.decided_at = "approved", actor, timezone.now()
    crew.version += 1
    place_locked(event, crew, actor)
    crew.save()
    audit.record(actor, "event.crew.approved", makerspace=event.makerspace, target=crew,
                 meta={"event_id": event.pk, "crew_id": crew.pk, "state": crew.state, "reason_code": reason})


@event_write(permission="manage_volunteers")
def add(event, *, actor, member, crew_role=""):
    require_feature(event)
    _open(event)
    if EventCrewMember.objects.filter(event=event, member=member, state__in=LIVE).exists():
        fail("crew_exists", "This person is already on the crew.")
    crew = EventCrewMember.objects.create(makerspace=event.makerspace, event=event, member=member,
                                          origin=EventCrewMember.Origin.STAFF, crew_role=crew_role)
    _approve_locked(event, crew, actor, reason="added_by_staff")
    from apps.events.notices_r2_l21a import crew_notice
    crew_notice(crew, "crew_invited")
    return crew


@event_write(permission="manage_volunteers")
def decide(event, *, actor, crew_id, approve, expected_version):
    require_feature(event)
    crew = get_object_or_404(EventCrewMember.objects.select_for_update(), pk=crew_id, event=event)
    if crew.version != expected_version:
        fail("stale_version", "This crew row changed. Refresh it.", version=crew.version)
    if crew.state != "applied":
        fail("invalid_transition", "Only a pending sign-up can be decided.")
    if approve:
        _open(event)
        _approve_locked(event, crew, actor, reason="reviewed")
    else:
        crew.state, crew.decided_by, crew.decided_at = "declined", actor, timezone.now()
        crew.version += 1
        crew.save()
        audit.record(actor, "event.crew.declined", makerspace=event.makerspace, target=crew,
                     meta={"event_id": event.pk, "crew_id": crew.pk, "state": crew.state})
    from apps.events.notices_r2_l21a import crew_notice
    crew_notice(crew, "crew_decided")
    return crew


@event_write
def end(event, *, actor, crew_id, own):
    """A member withdraws their own crew role, or staff remove someone; the free place goes."""
    from apps.events import event_authority
    require_feature(event)
    crew = get_object_or_404(EventCrewMember.objects.select_for_update().select_related("registration"),
                             pk=crew_id, event=event)
    if own and crew.member_id != actor.pk:
        fail("not_found", "Not found.", status=404)
    if not own:
        event_authority.require(actor, event, "manage_volunteers")
    if crew.state not in LIVE:
        fail("invalid_transition", "This crew role has already ended.")
    crew.state = "withdrawn" if own else "removed"
    crew.version += 1
    release_locked(crew, actor)
    crew.save()
    if own:
        audit.record(actor, "event.crew.withdrawn", makerspace=event.makerspace, target=crew,
                     meta={"event_id": event.pk, "crew_id": crew.pk, "state": crew.state})
    else:
        audit.record(actor, "event.crew.removed", makerspace=event.makerspace, target=crew,
                     meta={"event_id": event.pk, "crew_id": crew.pk, "state": crew.state})
    return crew
