"""Durable owner-only envelopes with IDs and deadlines, never answer values."""
from django.utils.translation import gettext
from apps.accounts.models import User
from apps.integrations.notification_outbox import emit
from apps.integrations.notification_sources import NotificationSource
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable
from apps.notifications.inbox import eligible_owner
from .response_models import StageFormAssignment
from .command_values import canonical_utc
from .trigger_service import participation_live
from apps.integrations.fanout_jobs import deferred_fanout


@deferred_fanout()
def enqueue_locked(assignment, kind, *, identity=None):
    space = assignment.event.makerspace
    if not module_enabled(space, "notifications"):
        return None
    recipient = User.objects.filter(pk=assignment.owner_member_id).first()
    if recipient is None:
        return None
    return emit(makerspace=space, recipient=recipient, feature="events", stream="events",
        event="stage_form." + kind, audience="member",
        dedup_key=f"stage:{assignment.pk}:{assignment.version}:{kind}:{identity or 'command'}",
        source_kind="event.stage_form", source_id=str(assignment.pk), revision=str(assignment.version), subject=assignment,
        context={"event_id": assignment.event_id, "assignment_id": assignment.pk, "version": assignment.version,
                 "due_revision": assignment.due_revision, "due_at": canonical_utc(assignment.effective_due_at),
                 "kind": kind, "reason_code": assignment.cancellation_reason_code if kind == "cancelled" else
                     assignment.reassignment_reason_code if kind == "reassigned" else ""},
        rendered=lambda: {"subject": gettext("Event stage form update"),
                  "text": gettext("Your stage form is %(state)s. Sign in to review its current deadline.") % {"state": kind.replace("_", " ")},
                  "link": f"/member/events/{assignment.event_id}/stage-forms/{assignment.stage_form_id}"})


def eligible(envelope):
    row = StageFormAssignment.objects.select_related("event__makerspace").filter(pk=envelope.source_id,
        event__makerspace_id=envelope.makerspace_id, owner_member_id=envelope.recipient_id).first()
    if row is None or not is_servable(row.event.makerspace) or not module_enabled(row.event.makerspace, "events"):
        return False
    if not eligible_owner(row.event.makerspace, row.owner_member_id) or str(row.version) != envelope.revision:
        return False
    kind = envelope.context.get("kind")
    if kind != "cancelled" and not participation_live(row):
        return False
    if row.event.status == "cancelled" and kind != "cancelled":
        return False
    if kind == "reminder":
        from django.utils import timezone
        return row.state == "open" and timezone.now() < row.effective_due_at
    return kind not in ("opened", "overdue") or row.state in ("open", "overdue")


NOTICE_SOURCE = NotificationSource(eligible)


@deferred_fanout()
def enqueue_warning_locked(subject, definition_ids, action):
    if not module_enabled(subject.event.makerspace, "notifications"):
        return
    recipient = User.objects.get(pk=subject.owner_member_id)
    for pk in definition_ids:
        emit(makerspace=subject.event.makerspace, recipient=recipient, feature="events", stream="events",
            event="stage_form.incomplete_warning", audience="member", source_kind="event.stage_warning", source_id=str(pk),
            revision=str(subject.event.version), subject=subject.event,
            dedup_key=f"stage-warning:{subject.event.pk}:{pk}:{subject.owner_member_id}:{subject.event.version}:{action}",
            context={"event_id": subject.event.pk, "stage_form_id": pk, "action": action},
            rendered=lambda: {"subject": gettext("An event form is incomplete"), "text": gettext("You may continue. Sign in to review your pending event form."),
                      "link": f"/member/events/{subject.event.pk}/stage-forms/{pk}"})


def eligible_warning(envelope):
    from apps.events.models import Event
    from .trigger_service import resolve_participant
    from .guards import readiness
    event = Event.objects.select_related("makerspace").filter(pk=envelope.context.get("event_id"), makerspace_id=envelope.makerspace_id).first()
    if not event or event.status == "cancelled" or not is_servable(event.makerspace) or not module_enabled(event.makerspace, "events"):
        return False
    if not eligible_owner(event.makerspace, envelope.recipient_id):
        return False
    subject = resolve_participant(event=event, owner_id=envelope.recipient_id)
    return int(envelope.source_id) in readiness(subject, envelope.context["action"])["warning_stage_form_ids"]


WARNING_NOTICE_SOURCE = NotificationSource(eligible_warning)
