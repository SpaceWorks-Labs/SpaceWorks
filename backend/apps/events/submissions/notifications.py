"""Source-backed submission status notices contain no project answers or files."""
from apps.accounts.staff_identity import person_q
from apps.accounts.models import User
from apps.events.submissions.models_projects import HackathonSubmission
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.integrations.notification_outbox import emit

SOURCE = "events.submission"
STATES = {"submit": "submitted", "amend": "locked", "withdraw": "withdrawn", "lock": "locked"}


def eligible(envelope):
    from apps.events.hackathons.admission_transactions import require_programme
    from rest_framework.exceptions import APIException
    from django.http import Http404
    row = HackathonSubmission.objects.select_related("event__makerspace").filter(pk=envelope.source_id,
        event_id=envelope.context.get("event_id"), version=envelope.revision).first()
    if row is None or row.event.makerspace_id != envelope.makerspace_id or envelope.event not in STATES or row.state != STATES[envelope.event]:
        return False
    try:
        require_programme(row.event)
    except (Http404, APIException):
        return False
    return row.team.memberships.filter(member_id=envelope.recipient_id, state="active").exists()


def render(envelope):
    from apps.integrations.notification_links import local_link
    return {"subject": "Your event project status changed", "text": "Open your event project to review its current submission status.",
        "link": local_link(envelope.makerspace, "member")}


def enqueue_locked(*, project, action):
    if action not in STATES:
        return
    if action in ("submit", "amend"):  # C-37: the submission receipt is a per-event switch, off for new events.
        from apps.events.judging.options import option
        if not option(project.event_id, "submission_receipt_email"):
            return
    ids = project.team.memberships.filter(state="active").values_list("member_id", flat=True)
    for member in User.objects.filter(person_q(), pk__in=ids, is_active=True, access_status="active",
            is_tenant_dump_stub=False).order_by("pk"):
        emit(makerspace=project.event.makerspace, recipient=member, feature="events", stream="events",
            event=action, audience="member", dedup_key=f"event-submission:{project.pk}:{project.version}:{member.pk}",
            source_kind=SOURCE, source_id=str(project.pk), revision=str(project.version), subject=project.event,
            context={"event_id": project.event_id}, rendered={})


def register():
    register_source(SOURCE, NotificationSource(eligible, render))
