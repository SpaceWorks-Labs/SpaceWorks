"""Organiser approval digest (G7, `events.approval_digest`).

Every 30 minutes, while sign-ups wait for approval, each organiser gets ONE summary for
the window: event titles and counts only, never a registrant's name or contact. The
envelope dedup key is the window, so a retried or overlapping sweep sends nothing twice,
and a window with nothing waiting sends nothing at all. Organisers are the space's event
staff (with the notification matrix's selections and mutes) plus per-event delegates
holding `manage_registrations`; each recipient only counts events they can manage.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.db.models import Count
from django.utils import timezone

from apps.audit.services import record
from apps.integrations.notification_outbox import emit
from apps.makerspaces.platform import feature_enabled, module_enabled
from apps.makerspaces.servability import servable_queryset
from apps.operations.cloud_jobs import bounded
from apps.separability.registry import runtime_active

logger = logging.getLogger(__name__)
SOURCE = "events.approval_digest"
EVENT = "approval_digest"
WINDOW = timedelta(minutes=30)
FEATURE = "events.approval_digest"


def window_start(now):
    return now.replace(minute=(now.minute // 30) * 30, second=0, microsecond=0)


def waiting(space, now):
    from .models import Event, EventRegistration
    rows = EventRegistration.objects.filter(
        event__makerspace=space, status=EventRegistration.Status.PENDING_APPROVAL,
        event__status=Event.Status.PUBLISHED, event__ends_at__gt=now)
    return list(rows.values("event_id", "event__title").annotate(count=Count("pk")).order_by("event_id"))


def _recipients(space, events):
    """(user, audience, manageable rows) for every organiser with something to approve."""
    from apps.accounts.models import User
    from apps.integrations.staff_notifications import staff_user_ids_for_feature
    from . import event_authority
    from .models import Event
    staff_ids = set(staff_user_ids_for_feature(space, "events", event=EVENT))
    by_id = {event.pk: event for event in Event.objects.filter(pk__in=[row["event_id"] for row in events])}
    from .grant_recipients import registration_grantees
    grantees = {user.pk: user for event in by_id.values() for user in registration_grantees(event)}
    for user in User.objects.filter(pk__in=staff_ids | set(grantees)).order_by("pk"):
        rows = [row for row in events if user.pk in staff_ids
                or event_authority.can(user, by_id[row["event_id"]], "manage_registrations")]
        if rows:
            yield user, "staff" if user.pk in staff_ids else "member", rows


def _render(space, rows):
    from apps.operations.notifications_p2 import staff_link
    total = sum(row["count"] for row in rows)
    lines = "\n".join(f"- {row['event__title']}: {row['count']} waiting" for row in rows[:20])
    noun = "sign-up waits" if total == 1 else "sign-ups wait"
    return {"subject": f"{total} {noun} for approval", "html": "",
            "text": f"{total} {noun} for your approval.\n\n{lines}\n\nOpen Events to approve or decline.",
            "link": staff_link(space, "events")}


def send_for_space(space, now=None):
    now = now or timezone.now()
    if not (module_enabled(space, "events") and feature_enabled(space, FEATURE)):
        return 0
    events = waiting(space, now)
    if not events:
        return 0
    window = window_start(now).isoformat()
    sent = 0
    for user, audience, rows in _recipients(space, events):
        emit(makerspace=space, recipient=user, feature="events", stream="events", event=EVENT,
             audience=audience, dedup_key=f"ev:approval-digest:{space.pk}:{user.pk}:{window}",
             source_kind=SOURCE, source_id=str(space.pk), revision=window[:64],
             context={"window": window, "event_ids": [row["event_id"] for row in rows]},
             rendered=_render(space, rows))
        sent += 1
    if sent:
        record(None, "event.approval_digest_sent", makerspace=space, target=space,
               meta={"recipients": sent, "waiting": sum(row["count"] for row in events), "window": window})
    return sent


def digest_eligible(envelope):
    """Live re-check: the switch is on, something still waits, the person can still manage it."""
    from apps.accounts.models import User
    from . import event_authority
    from .models import Event, EventRegistration
    space = envelope.makerspace
    if not (module_enabled(space, "events") and feature_enabled(space, FEATURE)):
        return False
    ids = envelope.context.get("event_ids") or []
    user = User.objects.filter(pk=envelope.recipient_id).first()
    pending = Event.objects.filter(pk__in=ids, makerspace=space, registrations__status=(
        EventRegistration.Status.PENDING_APPROVAL)).distinct()
    return bool(user) and any(event_authority.can(user, event, "manage_registrations") for event in pending)


@shared_task
def send_approval_digests_task():
    """Bounded: one page of servable spaces per run; each space is its own failure domain."""
    if not runtime_active("events"):
        return 0
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    from apps.makerspaces.scheduled_scope import live_space_ids
    spaces = servable_queryset().filter(pk__in=live_space_ids(FEATURE)).order_by("pk")
    counts = {"sent": 0, "failed": 0, "skipped": 0}
    for space in bounded.page(spaces, "event-approval-digest-spaces"):
        with fanout_tenant_write(space.pk, operation="event_approval_digest", counts=counts) as allowed:
            if not allowed:
                continue
            try:
                counts["sent"] += send_for_space(space)
            except Exception:
                counts["failed"] += 1
                logger.exception("event_approval_digest_failed", extra={"makerspace_id": space.pk})
    return counts
