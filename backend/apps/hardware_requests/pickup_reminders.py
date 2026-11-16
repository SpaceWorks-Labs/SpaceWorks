"""Pickup-expiring reminders (decision 221(f)): an accepted loan not yet collected.

`loans.pickup_windows` expires an accepted request at its pickup deadline. Before that, the
borrower gets ONE `pickup_expiring` reminder when the deadline is near: 24 hours ahead, or
half the window for a window shorter than two days, so a short window never reminds right
after the accept notice. There is no separate lead setting; the window itself
(`pickup_window_hours` or the member's own window end) decides.

The sweep runs inside `sweep_loan_pickups_task` (every 15 minutes), one tenant at a time.
The envelope's dedup key is bound to the deadline, so a repeated sweep reserves the same
intent and a moved deadline is a new reminder. At send, the request must still be accepted
with that same deadline, still ahead, and the feature still on.
"""

import logging
from datetime import timedelta

from django.utils import timezone
from django.utils.translation import gettext

from apps.accounts import rbac
from apps.integrations.notification_links import local_link
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.makerspaces.local_time import to_local

from .models import HardwareRequest
from .notifications_p2 import fanout, revision, safe_adapter

logger = logging.getLogger(__name__)
KIND = "hardware.pickup_reminder"
EVENT = "pickup_expiring"
FEATURE = "loans.pickup_windows"
LEAD = timedelta(hours=24)


def lead_for(row):
    """24 hours, or half the window when the window (accept -> deadline) is under two days."""
    if row.accepted_at is None:
        return LEAD
    return min(LEAD, (row.pickup_until - row.accepted_at) / 2)


def _revision(row):
    return revision(row.pk, row.pickup_until)


def _already_reserved(row):
    from apps.integrations.models_contract import NotificationEnvelope
    return rbac.scope_notification_policy(NotificationEnvelope.objects.all(), makerspace_id=row.makerspace_id).filter(
        source_kind=KIND, source_id=str(row.pk), revision=_revision(row)).exists()


@safe_adapter
def notify_pickup_expiring(row):
    space = row.makerspace
    until = to_local(space, row.pickup_until).strftime("%Y-%m-%d %H:%M %Z")
    own = {"subject": gettext("%(space)s: collect request #%(id)s soon") % {"space": space.name, "id": row.pk},
           "text": gettext("Your request #%(id)s is ready to collect. Collect it by %(until)s, or the reservation "
                           "is released.") % {"id": row.pk, "until": until}, "html": "", "link": local_link(space, "member")}
    owner = row.requester if not row.anonymous_idempotency_key_fingerprint else None
    return fanout(space=space, feature="hardware_requests", stream="hardware", event=EVENT, kind=KIND,
                  source=row.pk, version=_revision(row), subject=row, owner=owner, own=own,
                  context={"request_id": row.pk, "pickup_until": row.pickup_until.isoformat()})


def remind_expiring_pickups(*, now=None, limit=200):
    """Bounded sweep; each row runs inside its own skip-and-count tenant boundary."""
    from apps.makerspaces.scheduled_scope import live_space_ids
    from apps.operations.cloud_jobs import bounded
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    now = now or timezone.now()
    rows = rbac.scope_for_scheduled_work(HardwareRequest.objects.filter(
        status=HardwareRequest.Status.ACCEPTED, pickup_until__gt=now, pickup_until__lte=now + LEAD,
        makerspace_id__in=live_space_ids(FEATURE),
    )).select_related("makerspace", "requester").order_by("pickup_until", "id")
    counts = {"reminded": 0, "skipped": 0}
    acted = 0
    for row in bounded.page(rows, "loan-pickup-reminders"):
        # m9: the limit bounds rows ACTED on, not rows examined, so already-reminded rows at the front
        # of the deadline order cannot starve later ones.
        if acted >= max(int(limit), 1):
            break
        if row.pickup_until - now > lead_for(row):
            continue
        with fanout_tenant_write(row.makerspace_id, operation="loan_pickup_expiry", counts=counts) as go:
            if not go:
                continue
            if _already_reserved(row):
                continue
            acted += 1
            try:
                result = notify_pickup_expiring(row)
                counts["reminded"] += int(bool(result and result.scheduled))
            except Exception:
                counts["skipped"] += 1
                logger.exception("Pickup reminder failed for request %s", row.pk)
    return counts


def eligible(envelope):
    from apps.makerspaces.platform import feature_enabled
    row = rbac.scope_notification_policy(HardwareRequest.objects.all(), makerspace_id=envelope.makerspace_id).filter(
        pk=envelope.source_id).select_related("makerspace").first()
    return bool(row and envelope.audience == "requester" and envelope.event == EVENT
                and row.status == HardwareRequest.Status.ACCEPTED and row.pickup_until is not None
                and row.pickup_until > timezone.now() and _revision(row) == envelope.revision
                and row.requester_id == envelope.recipient_id and not row.anonymous_idempotency_key_fingerprint
                and feature_enabled(row.makerspace, FEATURE))


def register():
    register_source(KIND, NotificationSource(eligible))
