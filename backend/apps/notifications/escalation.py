"""Escalation re-ping for unseen urgent staff notices (X38, `notifications.escalation`).

One staff notice fans out to several people under one `event_key`. If none of them has
opened it after 30 minutes, it is escalated ONCE: each recipient's browser notification
is sent again (when they opted in), and the space's general chat rooms (rooms with no
machine/category scope) get a short re-ping that names only the feature and event --
no requester, no message text. Only events that wait on a staff decision escalate.
"""

from config.locale_resolution import override_for
from django.utils.translation import gettext
import logging
from datetime import timedelta

from celery import shared_task
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.services import record
from apps.operations.cloud_jobs import bounded

logger = logging.getLogger(__name__)
FEATURE = "notifications.escalation"
AFTER = timedelta(minutes=30)
HORIZON = timedelta(hours=24)
ESCALATING = {
    ("hardware_requests", "submitted"), ("printing", "submitted"),
    ("events", "registration_pending_approval"), ("bookings", "created"),
    ("members", "request_pending"), ("payments", "refund_request_received"),
}
ROOM_CHANNELS = ("telegram", "slack", "discord", "mattermost")


def unseen_keys(space, now):
    from django.db.models import Count, Max, Q
    from .models_inbox import NotificationInboxRow
    rows = NotificationInboxRow.objects.filter(makerspace=space, audience="staff",
                                               created_at__lte=now - AFTER, created_at__gt=now - HORIZON)
    match = Q()
    for feature, event in ESCALATING:
        match |= Q(feature=feature, event=event)
    groups = (rows.filter(match).values("event_key", "feature", "event")
              .annotate(seen=Count("pk", filter=Q(read_at__isnull=False)), latest=Max("created_at"))
              .filter(seen=0).order_by("latest")[:50])
    return list(groups)


def _rooms(space):
    from apps.integrations.models_destinations import NotificationDestination
    return (NotificationDestination.objects.filter(makerspace=space, is_active=True, channel__in=ROOM_CHANNELS,
                                                   machine_scopes__isnull=True, machine_type_scopes__isnull=True,
                                                   category_scopes__isnull=True).distinct().order_by("pk")[:5])


def escalate(space, group):
    from apps.integrations.dispatch_destination import deliver_text_to_destination
    from .browser_alerts import enqueue
    from .models_browser_alerts import NotificationEscalation
    from .models_inbox import NotificationInboxRow
    try:
        with transaction.atomic():
            row = NotificationEscalation.objects.create(makerspace=space, event_key=group["event_key"],
                                                        feature=group["feature"], event=group["event"])
    except IntegrityError:
        return False
    label = f"{group['feature'].replace('_', ' ')}: {group['event'].replace('_', ' ')}"
    posted = 0
    with override_for(makerspace=space):  # rooms have no single recipient: the makerspace default language
        room_text = gettext("Still waiting for staff: a %(label)s notice has not been opened for 30 minutes. "
                            "Open the staff console to act on it.") % {"label": label}
    for room in _rooms(space):
        ok, _error = deliver_text_to_destination(
            space, room, text=room_text,
            feature=group["feature"], event="escalation", reference=f"escalation-{row.pk}-{room.pk}")
        posted += int(bool(ok))
    for pk in NotificationInboxRow.objects.filter(makerspace=space, event_key=group["event_key"]).values_list(
            "pk", flat=True)[:20]:
        enqueue(pk)
    NotificationEscalation.objects.filter(pk=row.pk).update(rooms_posted=posted)
    record(None, "notification.escalated", makerspace=space, target=row,
           meta={"feature": group["feature"], "event": group["event"], "rooms": posted})
    return True


@shared_task
def escalate_unseen_task():
    from apps.makerspaces.servability import servable_queryset
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    from apps.makerspaces.scheduled_scope import live_space_ids
    counts = {"escalated": 0, "failed": 0, "skipped": 0}
    spaces = servable_queryset().filter(pk__in=live_space_ids(FEATURE)).order_by("pk")
    now = timezone.now()
    for space in bounded.page(spaces, "notification-escalation-spaces"):
        with fanout_tenant_write(space.pk, operation="notification_escalation", counts=counts) as allowed:
            if not allowed:
                continue
            for group in unseen_keys(space, now):
                try:
                    counts["escalated"] += int(escalate(space, group))
                except Exception:
                    counts["failed"] += 1
                    logger.warning("notification_escalation_failed", extra={"makerspace_id": space.pk})
    return counts
