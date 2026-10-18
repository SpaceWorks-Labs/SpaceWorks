"""Durable owner-only envelopes with IDs and deadlines, never answer values."""
from apps.accounts.models import User
from apps.integrations.notification_outbox import emit
from apps.integrations.notification_sources import NotificationSource
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable
from apps.notifications.inbox import eligible_owner
from .response_models import StageFormAssignment


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
                 "due_revision": assignment.due_revision, "kind": kind},
        rendered={"subject": "Event stage form update", "text": f"Your stage form is {kind.replace('_', ' ')}. Sign in to review its current deadline.",
                  "link": f"/member/events/{assignment.event_id}/stage-forms/{assignment.stage_form_id}"})


def eligible(envelope):
    row = StageFormAssignment.objects.select_related("event__makerspace").filter(pk=envelope.source_id,
        event__makerspace_id=envelope.makerspace_id, owner_member_id=envelope.recipient_id).first()
    if row is None or not is_servable(row.event.makerspace) or not module_enabled(row.event.makerspace, "events"):
        return False
    if not eligible_owner(row.event.makerspace, row.owner_member_id) or str(row.version) != envelope.revision:
        return False
    kind = envelope.context.get("kind")
    return kind not in ("opened", "reminder", "overdue") or row.state in ("open", "overdue")


NOTICE_SOURCE = NotificationSource(eligible)
