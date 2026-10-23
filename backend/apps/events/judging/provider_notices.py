"""Source-backed judging notices recheck assignments and released results."""

from apps.accounts.models import User
from apps.integrations.notification_outbox import emit
from apps.integrations.notification_sources import NotificationSource, register_source
from .models_results import JudgingNotice, ResultPublicationState
from .models_scoring import JudgeAssignment
from .ports import runtime

SOURCE = "events.judging"


def recipients(row):
    runtime().require_programme(row.event)
    if row.event.status != "published":
        return ()
    if row.kind in ("judge_assigned", "assignment_invalidated"):
        return assignment_recipients(row)
    if row.kind != "results_published" or not ResultPublicationState.objects.filter(event_id=row.event_id,
            current_announcement__result_id=row.source_id,
            current_announcement__result__version=row.revision).exists():
        return ()
    return tuple(sorted({pk for snapshot in runtime().snapshots(row.event_id)
                         if snapshot.current and snapshot.eligible for pk in snapshot.member_ids}))


def assignment_recipients(row):
    assignment = JudgeAssignment.objects.select_related("round").filter(
        pk=row.source_id, event_id=row.event_id, version=row.revision,
        round__event_id=row.event_id).first()
    expected_state = "assigned" if row.kind == "judge_assigned" else "invalidated"
    if assignment is None or assignment.state != expected_state:
        return ()
    judge = runtime().judge(assignment.judge_role_assignment_id)
    if not judge.active or judge.event_id != row.event_id:
        return ()
    if row.kind == "judge_assigned":
        from .conflicts import eligible as assignment_eligible
        snapshot = runtime().snapshot(assignment.submission_snapshot_id)
        if assignment.round.state != "open" or not assignment_eligible(judge, snapshot, assignment.round):
            return ()
    return (judge.member_id,)


def eligible(envelope):
    row = JudgingNotice.objects.select_related("event__makerspace").filter(
        pk=envelope.source_id, event_id=envelope.context.get("event_id"),
        revision=envelope.revision, kind=envelope.event).first()
    if row is None or row.event.makerspace_id != envelope.makerspace_id:
        return False
    from django.http import Http404
    from rest_framework.exceptions import APIException
    try:
        return envelope.recipient_id in recipients(row)
    except (Http404, APIException):
        return False


def render(envelope):
    from apps.integrations.notification_links import local_link
    if envelope.event in ("judge_assigned", "assignment_invalidated"):
        return {"subject": "Your judging work has changed", "text": "Open the event to review your current judging assignments.",
                "link": local_link(envelope.makerspace, "member")}
    return {"subject": "Event results are available", "text": "Open the event to review the published results.",
            "link": local_link(envelope.makerspace, "member")}


def deliver(notice_id):
    row = JudgingNotice.objects.select_related("event__makerspace").get(pk=notice_id)
    for user in User.objects.filter(pk__in=recipients(row), is_active=True, access_status="active",
                                    account_kind="member", is_tenant_dump_stub=False).order_by("pk"):
        emit(makerspace=row.event.makerspace, recipient=user, feature="events", stream="events",
            event=row.kind, audience="member", dedup_key=f"event-judging:{row.pk}:{row.revision}:{user.pk}",
            source_kind=SOURCE, source_id=str(row.pk), revision=str(row.revision), subject=row.event,
            context={"event_id": row.event_id}, rendered={})


def register():
    register_source(SOURCE, NotificationSource(eligible, render))
