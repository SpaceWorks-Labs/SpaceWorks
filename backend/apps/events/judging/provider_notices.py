"""Source-backed result notices; retries recheck publication and sealed recipients."""

from apps.accounts.models import User
from apps.integrations.notification_outbox import emit
from apps.integrations.notification_sources import NotificationSource, register_source
from .models_results import JudgingNotice, ResultPublicationState
from .ports import runtime

SOURCE = "events.judging"


def recipients(row):
    runtime().require_programme(row.event)
    if row.kind != "results_published" or not ResultPublicationState.objects.filter(event_id=row.event_id,
            current_announcement__result_id=row.source_id,
            current_announcement__result__version=row.revision).exists():
        return ()
    return tuple(sorted({pk for snapshot in runtime().snapshots(row.event_id)
                         if snapshot.current and snapshot.eligible for pk in snapshot.member_ids}))


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
