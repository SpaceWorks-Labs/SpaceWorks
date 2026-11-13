"""Finance-approved policy owner receives a live, redacted reviewer queue count."""
from django.utils.translation import gettext

from apps.accounts import rbac
from apps.events import event_authority
from apps.integrations.notification_outbox import emit
from apps.integrations.notification_sources import NotificationSource
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable
from .config_models import ReimbursementProgramme
from apps.integrations.fanout_jobs import deferred_fanout


@deferred_fanout()
def enqueue_locked(programme, *, operation_id, kind):
    if not module_enabled(programme.event.makerspace, "notifications"):
        return None
    return emit(makerspace=programme.event.makerspace, recipient=programme.approved_by,
        feature="events", stream="events", event="reimbursement.queue", audience="staff",
        dedup_key=f"reimbursement:queue:{programme.pk}:{operation_id}:{kind}",
        source_kind="event.reimbursement.queue", source_id=str(programme.pk), revision=str(programme.version),
        subject=programme, context={"event_id": programme.event_id, "kind": kind},
        rendered=lambda: {"subject": gettext("Travel support review queue"),
                          "text": gettext("Sign in to review the current queue."),
                          "link": f"/admin/events/{programme.event_id}/reimbursements"})


def eligible(envelope):
    row = ReimbursementProgramme.objects.select_related("event__makerspace", "approved_by").filter(pk=envelope.source_id,
        event__makerspace_id=envelope.makerspace_id, approved_by_id=envelope.recipient_id).first()
    return bool(row and str(row.version) == envelope.revision and is_servable(row.event.makerspace)
        and row.approved_by.is_active and row.approved_by.access_status == "active"
        and all(module_enabled(row.event.makerspace, key) for key in ("events", "event_reimbursements"))
        and (rbac.can(row.approved_by, rbac.Action.VIEW_FINANCE, row.event.makerspace_id)
             or event_authority.can(row.approved_by, row.event, "review_reimbursements")))


def render(envelope):
    from .request_models import GrantRequest
    count = GrantRequest.objects.filter(programme_id=envelope.source_id, state__in=("requested", "waitlisted")).count()
    return {"subject": gettext("Travel support review queue"),
        "text": gettext("%(count)s requests are awaiting review.") % {"count": count},
        "link": f"/admin/events/{envelope.context['event_id']}/reimbursements"}


NOTICE_SOURCE = NotificationSource(eligible, render)
