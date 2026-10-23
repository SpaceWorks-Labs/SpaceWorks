"""A published checklist milestone is an owner notice, never an admission offer."""
from apps.accounts.models import User
from apps.integrations.notification_outbox import emit
from apps.integrations.notification_sources import NotificationSource
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable
from apps.notifications.inbox import eligible_owner
from .milestone_models import EventStageMilestone


def enqueue_locked(marker):
    space = marker.event.makerspace
    if not module_enabled(space, "notifications"):
        return None
    return emit(makerspace=space, recipient=User.objects.get(pk=marker.member_id), feature="events", stream="events",
        event="stage_form.shortlisted", audience="member", dedup_key=f"stage-shortlist:{marker.pk}:{marker.version}",
        source_kind="event.stage_milestone", source_id=str(marker.pk), revision=str(marker.version), subject=marker,
        context={"event_id": marker.event_id, "milestone_id": marker.pk},
        rendered={"subject": "Event checklist update", "text": "A shortlist checklist milestone has been published. Sign in to review any event forms.",
                  "link": f"/member/events/{marker.event_id}"})


def eligible(envelope):
    row = EventStageMilestone.objects.select_related("event__makerspace").filter(pk=envelope.source_id,
        event__makerspace_id=envelope.makerspace_id, member_id=envelope.recipient_id, withdrawn_at__isnull=True).first()
    return bool(row and row.event.status != "cancelled" and str(row.version) == envelope.revision
        and is_servable(row.event.makerspace) and module_enabled(row.event.makerspace, "events")
        and eligible_owner(row.event.makerspace, row.member_id))


MILESTONE_NOTICE_SOURCE = NotificationSource(eligible)
