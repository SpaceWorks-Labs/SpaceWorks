"""Re-raise a venue fee whose first attempt failed (payments audit 0.12.0 B-9).

`venue_fees.on_event_published` charges the fee after commit and only logs a failure, so a
provider or pricing hiccup left the fee `configured` for good: the organiser was never billed
and nothing looked wrong. `charge` is already get-or-create idempotent (it locks the event and
the fee and refuses anything but `configured`), so retrying is safe. This pass picks up fees of
published, not-yet-ended events that stayed `configured` for ten minutes and charges them again,
one tenant and one fee at a time so a single failure never stops the rest.
"""

import logging
from datetime import timedelta

from django.utils import timezone

from apps.accounts import rbac
from apps.makerspaces.models import Makerspace
from apps.makerspaces.platform import feature_enabled
from apps.operations.cloud_jobs import bounded
from apps.tenant_migration.gate_runtime import fanout_tenant_write

from .models import Event
from .models_venue_fees import EventVenueFee

logger = logging.getLogger(__name__)
GRACE = timedelta(minutes=10)


def retry_unraised_venue_fees(*, limit=50):
    from .venue_fees import charge

    counts = {"charged": 0, "failed": 0}
    now = timezone.now()
    for space in bounded.page(rbac.scope_for_scheduled_work(Makerspace.objects.all(), field="pk").order_by("pk"),
                              "venue-fee-spaces"):
        if not feature_enabled(space, "events.venue_fees"):
            continue
        try:
            with fanout_tenant_write(space.pk, operation="retry_venue_fees", counts=counts) as allowed:
                if not allowed:
                    continue
                fees = EventVenueFee.objects.filter(
                    makerspace=space, status=EventVenueFee.Status.CONFIGURED, updated_at__lt=now - GRACE,
                    event__status=Event.Status.PUBLISHED, event__ends_at__gt=now,
                ).select_related("event").order_by("pk")[:bounded.limit(limit)]
                for fee in fees:
                    try:
                        charge(fee.event, actor=None)
                        counts["charged"] += 1
                    except Exception as exc:
                        counts["failed"] += 1
                        logger.error("event_venue_fee_retry_failed", extra={
                            "fee_id": fee.pk, "failure_type": type(exc).__name__})
        except Exception as exc:
            counts["failed"] += 1
            logger.error("event_venue_fee_retry_tenant_failed", extra={
                "makerspace_id": space.pk, "failure_type": type(exc).__name__})
    return counts
