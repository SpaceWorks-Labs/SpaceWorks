"""Safe personal envelopes with live source checks on every delivery retry."""
from django.utils import timezone
from apps.accounts.models import User
from apps.integrations.notification_outbox import emit
from apps.integrations.notification_sources import NotificationSource, register_source
from .models_notices import EventContributorNotice

CONTRIBUTION_SOURCE = "events.contributor"
HELP_SOURCE = "events.mentor_help"


def contribution_recipients(row):
    from apps.makerspaces.platform import feature_enabled, module_enabled
    from apps.makerspaces.servability import is_servable
    event = row.event
    if not is_servable(event.makerspace) or not module_enabled(event.makerspace, "events"):
        return ()
    if row.signup_id:
        signup = row.signup
        if not feature_enabled(event.makerspace, "events.volunteering"):
            return ()
        if row.kind == "cancelled":
            return (signup.member_id,) if signup.shift.version == row.generation and (
                signup.state == "withdrawn" or signup.shift.state == "closed") else ()
        if (event.status != "published" or not feature_enabled(event.makerspace, "events.volunteering")
                or signup.state != "approved" or signup.assignment.state != "approved"
                or signup.assignment.imported_inert or signup.shift.state != "open"
                or signup.shift.version != row.generation or signup.shift.ends_at <= timezone.now()):
            return ()
        return (signup.member_id,)
    if not feature_enabled(event.makerspace, "events.mentoring") or row.booking.state != "cancelled":
        return ()
    return tuple(pk for pk in (row.booking.booked_by_id, row.booking.mentor_assignment.member_id) if pk)


def contribution_eligible(envelope):
    if envelope.event != "contribution_update":
        return False
    row = EventContributorNotice.objects.select_related("event__makerspace").filter(
        pk=envelope.source_id, event_id=envelope.context.get("event_id"),
        generation=envelope.revision).first()
    return bool(row and row.makerspace_id == envelope.makerspace_id
        and envelope.recipient_id in contribution_recipients(row))


def help_eligible(envelope):
    if envelope.event != "mentor_help_update":
        return False
    from apps.events.mentoring.models_rounds import MentorNotificationIntent
    from apps.events.mentoring.notifications import recipients
    from apps.events.mentoring.help_expiry import deadline
    from .runtime import ContributorPorts
    from apps.makerspaces.platform import feature_enabled, module_enabled
    from apps.makerspaces.servability import is_servable
    row = MentorNotificationIntent.objects.select_related("event__makerspace", "request__type").filter(
        pk=envelope.source_id, event_id=envelope.context.get("event_id"), generation=envelope.revision).first()
    if (row is None or row.makerspace_id != envelope.makerspace_id or row.request.practice_run_id
            or row.event.status != "published"
            or not is_servable(row.event.makerspace) or not module_enabled(row.event.makerspace, "events")
            or not feature_enabled(row.event.makerspace, "events.mentoring")):
        return False
    if row.kind in ("created", "attention") and (row.request.state != "open"
            or deadline(row.request, row.event) <= timezone.now()):
        return False
    if row.kind == "attention" and row.generation != row.request.open_generation:
        return False
    ids = ContributorPorts().organizer_ids(event_id=row.event_id) if row.kind == "attention" else recipients(row.request, row.event)
    return envelope.recipient_id in ids


def deliver_contribution(*, notice_id, idempotency_key):
    row = EventContributorNotice.objects.select_related("event__makerspace").get(pk=notice_id)
    for member in User.objects.filter(pk__in=contribution_recipients(row), account_kind="member", is_active=True, access_status="active",
            is_tenant_dump_stub=False):
        emit(makerspace=row.event.makerspace, recipient=member, feature="events", stream="events",
            event="contribution_update", audience="member", source_kind=CONTRIBUTION_SOURCE,
            source_id=str(row.pk), revision=str(row.generation), subject=row,
            dedup_key=f"{idempotency_key}:{member.pk}", context={"event_id": row.event_id},
            rendered={"subject": "Your event contribution", "text": "Open the event to review your duty or office-hour booking."})


def deliver_help(*, intent_id, recipient_ids, payload, idempotency_key):
    from apps.events.mentoring.models_rounds import MentorNotificationIntent
    row = MentorNotificationIntent.objects.select_related("event__makerspace").get(pk=intent_id)
    for member in User.objects.filter(pk__in=recipient_ids, account_kind="member", is_active=True, access_status="active", is_tenant_dump_stub=False):
        emit(makerspace=row.event.makerspace, recipient=member, feature="events", stream="events",
            event="mentor_help_update", audience="member", source_kind=HELP_SOURCE,
            source_id=str(row.pk), revision=str(row.generation), subject=row,
            dedup_key=f"{idempotency_key}:{member.pk}", context={"event_id": row.event_id},
            rendered={"subject": "Mentor Desk update", "text": "Open Mentor Desk to review the current help queue."})


def enqueue(*, kind, notice_id):
    # Persisted sweeps remain the recovery path when broker dispatch fails.
    from apps.events.tasks_contributions import sweep_contributor_maintenance_task
    sweep_contributor_maintenance_task.delay()


def register():
    register_source(CONTRIBUTION_SOURCE, NotificationSource(contribution_eligible))
    register_source(HELP_SOURCE, NotificationSource(help_eligible))
    from .role_notices import register as register_roles
    register_roles()
