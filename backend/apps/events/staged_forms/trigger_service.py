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
    if registration is None:
        registration = EventRegistration.objects.filter(event=event, member_id=owner_id).order_by("-created_at", "-pk").first()
    return Participant(event, owner_id, registration, application, creation_operation_id)


def participation_live(row):
    return not (row.registration_id and row.registration.status in ("cancelled", "rejected")) and not (
        row.application_id and row.application.state in ("rejected", "declined", "expired", "withdrawn"))


def require_virtual_context(event, actor):
    """A guessed event ID/creation UUID cannot expose an unpublished signup."""
    from apps.events.registration_access import require_registration_access
    from apps.events.capacity import registration_is_open
    from apps.events.hackathons.admission_models import HackathonConfig
    from apps.events.hackathons.admission_workflow import require_application_open
    from apps.payments.event_payouts.errors import require
    if event.is_public:
        require_registration_access(event, actor)
    else:
        from apps.events.views_member_events import _collaborative_events, _active_membership
        from apps.makerspaces.models import MakerspaceMembership
        from apps.presence.guard import MemberPresenceRequired
        from types import SimpleNamespace
        allowed = False
        for membership in MakerspaceMembership.objects.filter(user=actor, status="active").select_related("makerspace"):
            if not _collaborative_events(membership.makerspace).filter(pk=event.pk).exists():
                continue
            try:
                _active_membership(SimpleNamespace(user=actor), membership.makerspace_id)
                require_registration_access(event, actor, collaborative=True, via=membership.makerspace)
            except MemberPresenceRequired:
                continue
            allowed = True
            break
        require(allowed, "not_found", status=404)
    config = HackathonConfig.objects.filter(event=event, enabled=True).first()
    if config:
        require_application_open(event, config, timezone.now())
    else:
        require(registration_is_open(event, timezone.now()), "registration_closed")


def registration_accepted_at(registration):
    from django.db.models import Q
    from apps.audit.models import AuditLog
    # Use published canonical history, not an edit timestamp or initial pending
    # registration time. Legacy rows without that history remain conservative.
    marker = AuditLog.objects.filter(makerspace_id=registration.event.makerspace_id,
        target_type="events.eventregistration", target_id=str(registration.pk)).filter(
        Q(action="event.registration_promoted") |
        Q(action="event.registration_approved", meta__new_status="registered") |
        Q(action="event.registration_created", meta__status="registered")).order_by("created_at", "pk").first()
    return marker.created_at if marker else registration.created_at


def matches_audience(definition, subject):
    audience = validate_audience(definition.audience)
    if audience["roles"] or audience["track_ids"]:
        from apps.events.contributions.models_roles import EventRoleAssignment
        rows = list(EventRoleAssignment.objects.filter(event=subject.event, member_id=subject.owner_member_id,
            state__in=("approved", "completed"), imported_inert=False))
        roles = {row.role for row in rows} | ({"participant"} if subject.registration or subject.application or subject.creation_operation_id else set())
        tracks = {track for row in rows for track in row.track_ids}
        from apps.events.submissions.models import HackathonSubmission
        from apps.events.hackathons.team_models import HackathonTeamMember
        teams = HackathonTeamMember.objects.filter(event=subject.event, member_id=subject.owner_member_id,
            state="active", team__state__in=("forming", "locked")).values("team_id")
        for selected in HackathonSubmission.objects.filter(event=subject.event, team_id__in=teams).exclude(
            state__in=("withdrawn", "disqualified")).values_list("track_ids", flat=True):
            tracks.update(selected)
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
    if subject.event.status == "cancelled":
        return None
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
        return registration_accepted_at(registration) if registration and registration.status in ("registered", "attended") else None
    if definition.stage == "application":
        if application:
            return application.submitted_at or (timezone.now() if subject.creation_operation_id else None)
        return registration.created_at if registration else (timezone.now() if subject.creation_operation_id else None)
    if not registration or registration.status not in ("registered", "attended"):
        return None
    return subject.event.starts_at if definition.stage == "pre_event" else subject.event.ends_at


def schedule(definition, *, subject, triggered_at):
    return resolve(triggered_at=triggered_at, event_start=subject.event.starts_at, event_end=subject.event.ends_at,
        **{key: getattr(definition, key) for key in ("opening_mode", "due_mode", "opens_at",
            "opening_offset_seconds", "due_at", "due_after_seconds", "due_event_offset_seconds")})


def applicable(definition, subject, *, now=None, include_future=False):
    if definition.state != "published" or definition.event_id != subject.event.pk:
        return None
    triggered = trigger_at(definition, subject)
    if triggered is None:
        return None
    # Read the clock after the trigger: an inline (virtual) child triggers "now", and a
    # clock read taken first would place that opening in the future and refuse it.
    now = now or timezone.now()
    # Publishing does not retroactively activate someone who passed the trigger.
    # Explicit catch-up creates an assignment with its reviewed future deadline.
    if triggered < definition.published_at:
        return None
    value = schedule(definition, subject=subject, triggered_at=triggered)
    return (triggered, value) if include_future or value.opens_at <= now else None
