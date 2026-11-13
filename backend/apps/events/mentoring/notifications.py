"""Recoverable safe-reference outbox. Provider calls happen outside row locks."""
import logging
from datetime import timedelta
from uuid import uuid4
from django.db import transaction
from apps.events.services_write_boundary import write_boundary
from django.utils import timezone
from apps.audit.services import record
from apps.events.models import Event
from apps.events.contributions.models_roles import EventRoleAssignment
from apps.events.contributions.ports import ports
from apps.makerspaces.guards import require_feature, require_module_locked
from apps.tenant_migration.gate_runtime import boundary_tenant_write
from .models_rounds import MentorNotificationIntent
from .models_queue import EventHelpRequest
from . import policy

logger = logging.getLogger(__name__)


def recipients(request, event):
    ids = []
    for role in EventRoleAssignment.objects.filter(event=event, role="mentor",
            state="approved", imported_inert=False).select_related("member"):
        try:
            assignment, profile = policy.mentor_for(role.member, event, assignment_id=role.pk)
            if policy.request_eligible(assignment=assignment, profile=profile, row=request,
                    skill_tags=request.type.skill_tags, priority_until=request.exclusive_until):
                ids.append(role.member_id)
        except Exception as exc:
            from rest_framework.exceptions import APIException
            if isinstance(exc, APIException) and exc.status_code in (403, 404):
                continue
            raise
    return tuple(sorted(set(ids)))


def deliver_one(intent_id):
    adapter = ports()
    seed = MentorNotificationIntent.objects.get(pk=intent_id)
    with write_boundary(seed.event):
        event = Event.objects.select_for_update().get(pk=seed.event_id)
        event.makerspace = require_module_locked(event.makerspace_id, "events")
        require_feature(event.makerspace, "events.mentoring")
        adapter.require_event_feature(event_id=event.pk, feature="events.mentoring")
        row = MentorNotificationIntent.objects.select_for_update().get(pk=intent_id)
        now = timezone.now()
        if row.delivered_at or row.available_at > now or row.attempts >= 15 or (row.claim_until and row.claim_until > now):
            return False
        token = uuid4()
        row.claim_uuid, row.claim_until = token, now + timedelta(minutes=2)
        row.attempts += 1
        row.save(update_fields=["claim_uuid", "claim_until", "attempts"])
        record(None, "event.mentor_notice.claimed", makerspace=event.makerspace, target=row,
               meta={"attempt": row.attempts})
    try:
        # Re-read persisted state immediately before delivery. Adapter repeats
        # recipient/source/feature checks on provider retry, using the same key.
        request = EventHelpRequest.objects.select_related("type").get(pk=row.request_id)
        event = Event.objects.select_related("makerspace").get(pk=event.pk)
        require_feature(event.makerspace, "events.mentoring")
        adapter.require_event_feature(event_id=event.pk, feature="events.mentoring")
        stale_alert = row.kind in ("created", "attention") and request.state != "open"
        if row.kind in ("created", "attention"):
            from .help_expiry import deadline
            stale_alert = stale_alert or deadline(request, event) <= timezone.now()
        if row.kind == "attention" and row.generation != request.open_generation:
            stale_alert = True
        if request.practice_run_id is not None or stale_alert:
            recipient_ids = ()
        else:
            recipient_ids = adapter.organizer_ids(event_id=event.pk) if row.kind == "attention" else recipients(request, event)
        if recipient_ids:
            payload = {
                "event_id": event.pk, "team_alias": policy.request_alias(request, event),
                "category": request.type.key, "priority": request.priority,
                "navigation_path": f"/staff/events/{event.pk}/mentor-desk"}
            adapter.deliver_help(intent_id=row.pk, recipient_ids=recipient_ids, payload=payload,
                                 idempotency_key=f"event-help:{row.pk}:{row.generation}")
            # G9: the event's chosen team rooms, only while mentors are on shift (fail-safe).
            from .chat_alerts import post_help_alert
            post_help_alert(row, event, payload, recipient_ids)
    except Exception:
        logger.warning("event_mentor_notice_retry", extra={"intent_id": row.pk, "attempt": row.attempts})
        success = False
    else:
        success = True
    with write_boundary(seed.event):
        Event.objects.select_for_update().get(pk=seed.event_id)
        current = MentorNotificationIntent.objects.select_for_update().get(pk=intent_id)
        if current.claim_uuid != token:
            return False
        current.claim_uuid = current.claim_until = None
        if success:
            current.delivered_at = timezone.now()
        else:
            current.available_at = timezone.now() + timedelta(seconds=min(3600, 30 * 2 ** current.attempts))
        current.save(update_fields=["claim_uuid", "claim_until", "delivered_at", "available_at"])
        record(None, "event.mentor_notice.delivered" if success else "event.mentor_notice.retry",
               makerspace=event.makerspace, target=current, meta={"attempt": current.attempts})
    return success


def sweep(*, limit=100):
    ids = MentorNotificationIntent.objects.filter(delivered_at__isnull=True,
        available_at__lte=timezone.now(), attempts__lt=15).order_by("available_at", "pk").values_list("pk", flat=True)[:min(limit, 100)]
    return sum(bool(deliver_one(pk)) for pk in list(ids))


def escalate(*, event_id):
    adapter = ports()
    seed = Event.objects.get(pk=event_id)
    with write_boundary(seed):
        with transaction.atomic():
            event = Event.objects.select_for_update().get(pk=event_id)
            event.makerspace = require_module_locked(event.makerspace_id, "events")
            require_feature(event.makerspace, "events.mentoring")
            adapter.require_event_feature(event_id=event.pk, feature="events.mentoring")
            rows = EventHelpRequest.objects.filter(event=event, state="open", practice_run_id__isnull=True,
                last_opened_at__lte=timezone.now() - timedelta(minutes=15),
                event__ends_at__gt=timezone.now()).exclude(expires_at__lte=timezone.now())
            count = 0
            for request in rows:
                intent, created = MentorNotificationIntent.objects.get_or_create(request=request,
                    kind="attention", generation=request.open_generation, defaults={"event": event,
                        "makerspace_id": event.makerspace_id, "available_at": timezone.now()})
                if created:
                    from apps.events.contributions.notifications import enqueue_on_commit
                    enqueue_on_commit(kind="mentor_help", notice_id=intent.pk)
                    record(None, "event.help.attention", makerspace=event.makerspace, target=intent)
                    count += 1
            return count
