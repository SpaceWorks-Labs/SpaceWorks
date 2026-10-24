"""Time-specific reminders and cancellation receipts; never include form answers."""
import logging
from datetime import datetime, time, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo
from uuid import uuid4
from django.db import transaction
from apps.events.services_write_boundary import write_boundary
from django.utils import timezone
from apps.audit.services import record
from apps.events.models import Event
from apps.makerspaces.guards import require_feature, require_module_locked
from apps.tenant_migration.gate_runtime import boundary_tenant_write
from .models_notices import EventContributorNotice
from .ports import ports

logger = logging.getLogger(__name__)


def enqueue_on_commit(*, kind, notice_id):
    def enqueue():
        try:
            ports().enqueue_notice(kind=kind, notice_id=notice_id)
        except Exception:
            logger.warning("event_notice_enqueue_deferred", extra={"kind": kind, "notice_id": notice_id})
    transaction.on_commit(enqueue)


def schedule_signup_locked(signup):
    now = timezone.now()
    starts = signup.shift.starts_at
    zone = ZoneInfo(signup.event.timezone_name)
    day_of = datetime.combine(starts.astimezone(zone).date(), time.min, zone).astimezone(dt_timezone.utc)
    for kind, when in (("week", starts - timedelta(days=7)), ("two_days", starts - timedelta(days=2)), ("day_of", day_of)):
        if when < now:
            continue
        notice, created = EventContributorNotice.objects.get_or_create(signup=signup, kind=kind, generation=signup.shift.version,
            defaults={"event_id": signup.event_id, "makerspace_id": signup.makerspace_id, "available_at": when})
        if created:
            enqueue_on_commit(kind="contribution", notice_id=notice.pk)


def cancelled_booking_locked(booking):
    notice, created = EventContributorNotice.objects.get_or_create(booking=booking, kind="booking_cancelled", generation=booking.version,
        defaults={"event_id": booking.event_id, "makerspace_id": booking.makerspace_id, "available_at": timezone.now()})
    if created:
        enqueue_on_commit(kind="contribution", notice_id=notice.pk)


def cancelled_signup_locked(signup):
    notice, created = EventContributorNotice.objects.get_or_create(signup=signup, kind="cancelled",
        generation=signup.shift.version, defaults={"event_id": signup.event_id,
            "makerspace_id": signup.makerspace_id, "available_at": timezone.now()})
    if created:
        enqueue_on_commit(kind="contribution", notice_id=notice.pk)


def deliver_one(notice_id):
    seed = EventContributorNotice.objects.get(pk=notice_id)
    adapter = ports()
    with write_boundary(seed.event):
        event = Event.objects.select_for_update().get(pk=seed.event_id)
        event.makerspace = require_module_locked(event.makerspace_id, "events")
        feature = "events.volunteering" if seed.signup_id else "events.mentoring"
        require_feature(event.makerspace, feature)
        adapter.require_event_feature(event_id=event.pk, feature=feature)
        row = EventContributorNotice.objects.select_for_update().get(pk=notice_id)
        now = timezone.now()
        if row.delivered_at or row.available_at > now or row.attempts >= 15 or (row.claim_until and row.claim_until > now):
            return False
        token = uuid4()
        row.claim_uuid, row.claim_until = token, now + timedelta(minutes=2)
        row.attempts += 1
        row.save(update_fields=["claim_uuid", "claim_until", "attempts"])
        record(None, "event.contributor_notice.claimed", makerspace=event.makerspace, target=row,
               meta={"attempt": row.attempts})
    try:
        # Provider rechecks user/team/role/shift/window and current capability
        # on each actual delivery. A stale scheduled notice is a successful no-op.
        adapter.deliver_contribution(notice_id=row.pk,
            idempotency_key=f"event-contribution:{row.pk}:{row.generation}")
    except Exception:
        logger.warning("event_contributor_notice_retry", extra={"notice_id": row.pk, "attempt": row.attempts})
        success = False
    else:
        success = True
    with write_boundary(seed.event):
        Event.objects.select_for_update().get(pk=seed.event_id)
        row = EventContributorNotice.objects.select_for_update().get(pk=notice_id)
        if row.claim_uuid != token:
            return False
        row.claim_uuid = row.claim_until = None
        if success:
            row.delivered_at = timezone.now()
        else:
            row.available_at = timezone.now() + timedelta(seconds=min(3600, 30 * 2 ** row.attempts))
        row.save(update_fields=["claim_uuid", "claim_until", "delivered_at", "available_at"])
        record(None, "event.contributor_notice.delivered" if success else "event.contributor_notice.retry",
               makerspace=event.makerspace, target=row, meta={"attempt": row.attempts})
        return success


def sweep(limit=100):
    ids = EventContributorNotice.objects.filter(delivered_at__isnull=True, available_at__lte=timezone.now(),
        attempts__lt=15).order_by("available_at", "pk").values_list("pk", flat=True)[:min(limit, 100)]
    return sum(bool(deliver_one(pk)) for pk in list(ids))
