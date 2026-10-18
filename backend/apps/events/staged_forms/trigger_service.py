"""One read-only coverage evaluator for hooks, readiness and canonical guards."""
from dataclasses import dataclass
from django.utils import timezone
from apps.events.models import EventRegistration, HackathonApplication
from .milestone_models import EventStageMilestone
from .deadlines import resolve
from .policy import validate_audience


@dataclass(frozen=True)
class Participant:
    event: object
    owner_member_id: int
    registration: object = None
    application: object = None
    creation_operation_id: object = None


def resolve_participant(*, event, owner_id, creation_operation_id=None):
    application = HackathonApplication.objects.filter(event=event, member_id=owner_id).first()
    registration = (application.registration if application and application.registration_id else
        EventRegistration.objects.filter(event=event, member_id=owner_id,
            status__in=("pending_approval", "waitlisted", "registered", "attended")).first())
    return Participant(event, owner_id, registration, application, creation_operation_id)


def matches_audience(definition, subject):
    audience = validate_audience(definition.audience)
    if audience["roles"] or audience["track_ids"]:
        from apps.events.contributions.models_roles import EventRoleAssignment
        rows = list(EventRoleAssignment.objects.filter(event=subject.event, member_id=subject.owner_member_id,
            state__in=("approved", "accepted", "active", "completed"), imported_inert=False))
        roles = {row.role for row in rows} | ({"participant"} if subject.registration or subject.application else set())
        tracks = {track for row in rows for track in row.track_ids}
        if audience["roles"] and not roles.intersection(audience["roles"]):
            return False
        if audience["track_ids"] and not tracks.intersection(audience["track_ids"]):
            return False
    if audience["travel_requested"] is not None:
        # Query only retained declarations; module state cannot change frozen
        # assignment applicability. R runtime is not imported by this evaluator.
        from django.apps import apps
        model = apps.get_model("event_reimbursements", "GrantRequest")
        requested = model.objects.filter(event=subject.event, member_id=subject.owner_member_id).exclude(
            state__in=("draft", "withdrawn", "expired")).exists()
        if requested != audience["travel_requested"]:
            return False
    return True


def trigger_at(definition, subject):
    registration, application = subject.registration, subject.application
    if registration and registration.status in ("cancelled", "rejected"):
        return None
    if application and application.state in ("rejected", "declined", "expired", "withdrawn"):
        return None
    if not matches_audience(definition, subject):
        return None
    if definition.stage == "shortlisted":
        marker = EventStageMilestone.objects.filter(event=subject.event, member_id=subject.owner_member_id,
            kind="shortlisted", withdrawn_at__isnull=True).first()
        return marker.published_at if marker else None
    if definition.stage == "accepted_rsvp":
        if application:
            if definition.activation_point == "accepted":
                return application.offered_at if application.state in ("offered", "confirmed") else None
            return application.rsvp_accepted_at if application.state == "confirmed" else None
        return registration.created_at if registration and registration.status in ("registered", "attended") else None
    if definition.stage == "application":
        if application:
            return application.submitted_at
        return registration.created_at if registration else (timezone.now() if subject.creation_operation_id else None)
    if not registration or registration.status not in ("registered", "attended"):
        return None
    return subject.event.starts_at if definition.stage == "pre_event" else subject.event.ends_at


def schedule(definition, *, subject, triggered_at):
    return resolve(triggered_at=triggered_at, event_start=subject.event.starts_at, event_end=subject.event.ends_at,
        **{key: getattr(definition, key) for key in ("opening_mode", "due_mode", "opens_at",
            "opening_offset_seconds", "due_at", "due_after_seconds", "due_event_offset_seconds")})


def applicable(definition, subject, *, now=None):
    now = now or timezone.now()
    if definition.state != "published" or definition.event_id != subject.event.pk:
        return None
    triggered = trigger_at(definition, subject)
    if triggered is None:
        return None
    # Publishing does not retroactively activate someone who passed the trigger.
    # Explicit catch-up creates an assignment with its reviewed future deadline.
    if triggered < definition.published_at:
        return None
    value = schedule(definition, subject=subject, triggered_at=triggered)
    return (triggered, value) if value.opens_at <= now else None
