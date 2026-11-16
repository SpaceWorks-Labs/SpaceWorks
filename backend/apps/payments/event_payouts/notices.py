"""Transactional personal core notices. No payee value, filename or reason text."""
from django.utils.translation import gettext
from django.db import connection
from apps.accounts.models import User
from apps.integrations.notification_outbox import emit
from apps.integrations.notification_sources import NotificationSource
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable
from apps.notifications.inbox import eligible_owner
from .obligation_models import EventPayoutObligation
from apps.integrations.fanout_jobs import deferred_fanout

KINDS = frozenset(("approved", "decision_corrected", "cancelled", "payment_recorded", "payment_corrected",
    "payee_submitted", "payee_verified", "payee_correction", "held", "hold_released", "details_reminder"))


@deferred_fanout()
def enqueue_locked(obligation, kind, *, identity="command"):
    if kind not in KINDS or not connection.in_atomic_block:
        raise ValueError("A supported core notice requires the owning transaction.")
    space = obligation.makerspace
    if (not is_servable(space) or not module_enabled(space, "notifications")
            or not eligible_owner(space, obligation.owner_member_id)):
        return None
    owner = User.objects.get(pk=obligation.owner_member_id)
    return emit(makerspace=space, recipient=owner, feature="payments", stream="payments",
        event="event_payout." + kind, audience="member",
        dedup_key=f"payout:{obligation.pk}:{obligation.version}:{kind}:{identity}",
        source_kind="finance.event_payout", source_id=str(obligation.pk), revision=str(obligation.version), subject=obligation,
        context={"obligation_id": str(obligation.pk), "version": obligation.version, "kind": kind},
        rendered=lambda: {"subject": gettext("Event reimbursement update"), "text": gettext("Your reimbursement record has an update. Sign in to review it."),
                  "link": f"/member/event-payouts/{obligation.pk}"})


def eligible(envelope):
    row = EventPayoutObligation.objects.select_related("makerspace").filter(pk=envelope.source_id,
        makerspace_id=envelope.makerspace_id, owner_member_id=envelope.recipient_id).first()
    if (row is None or not is_servable(row.makerspace) or not module_enabled(row.makerspace, "notifications")
            or not eligible_owner(row.makerspace, row.owner_member_id) or str(row.version) != envelope.revision):
        return False
    kind = envelope.context.get("kind")
    if kind not in KINDS:
        return False
    if kind == "details_reminder":
        from .reminders import needs_details
        return needs_details(row)
    if kind == "cancelled":
        return row.state == "cancelled"
    return True


NOTICE_SOURCE = NotificationSource(eligible)
