"""Durable, source-backed date review notices for all three answer subjects."""
from apps.events.contracts.subjects import SubjectKind
from apps.events.answer_derivations.subjects import subject_model, require_event

SOURCE = "events.answer_date"


def eligible(envelope):
    from rest_framework.exceptions import APIException
    try:
        kind = SubjectKind(envelope.context.get("subject_kind"))
        row = subject_model(kind).objects.filter(pk=envelope.source_id,
            event_id=envelope.context.get("event_id"), member_id=envelope.recipient_id,
            date_review_required=True).select_related("event__makerspace", "member").first()
        if row is None or row.event.makerspace_id != envelope.makerspace_id:
            return False
        if row.event.status == "cancelled":
            return False
        require_event(row.event)
        return bool(str(row.event.event_date_revision) == envelope.revision and row.member
            and row.member.is_active and row.member.access_status == "active"
            and row.member.account_kind == "member" and not row.member.is_tenant_dump_stub)
    except (ValueError, APIException):
        return False


def register_date_notices():
    """G startup must register this in workers as well as web processes."""
    from apps.integrations.notification_sources import NotificationSource, register_source
    register_source(SOURCE, NotificationSource(eligible))


def enqueue_locked(*, event, row, kind):
    from apps.integrations.notification_outbox import emit
    if row.member_id is None:
        return
    emit(makerspace=event.makerspace, recipient=row.member, feature="events", stream="events",
        event="answer_date_review", audience="requester", source_kind=SOURCE, source_id=str(row.pk),
        revision=str(event.event_date_revision), subject=row,
        dedup_key=f"event-date:{event.pk}:{event.event_date_revision}:{kind.value}:{row.pk}",
        context={"event_id": event.pk, "subject_kind": kind.value},
        rendered={"subject": "Review your event answers", "text":
            "The event start date or timezone changed. Review your answers at the current event date."})
