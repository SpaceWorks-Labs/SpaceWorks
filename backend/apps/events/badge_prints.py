"""Badge print receipts and the monthly print limit (parity E-B2).

A receipt is the append-only record that one badge was printed (desk, PIN station, offline desk or a bulk job).
Receipts are idempotent by `operation_id`, so a retrying or syncing device never double-counts. The
`event_badge_prints_monthly` limit (decision 284, default none) refuses only an online print START and a bulk
job; offline prints are never blocked and are counted when they sync, and issuing a card, a holder downloading
their own card and verification are never limited.
"""
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.audit import services as audit
from apps.makerspaces.platform import feature_enabled

from .models import EventIdCard, EventRegistration
from .models_badge_prints import EventBadgePrint
from .services_write_boundary import event_write

FEATURE = "events.badge_desk_print"
BATCH_MAX = 200
LIMIT_KEY = "event_badge_prints_monthly"


def desk_print_on(makerspace):
    from apps.card_designs.switches import event_cards_on
    return event_cards_on(makerspace) and feature_enabled(makerspace, FEATURE)


def require_desk_print(event):
    if not desk_print_on(event.makerspace):
        raise NotFound()


def check_print_start(event, adding=1):
    """Refuse an online print start or a bulk job once the space has used its monthly allowance."""
    from apps.managed_hosting.extra_quotas import check_extra_quota
    check_extra_quota(event.makerspace, LIMIT_KEY, adding=adding)


def _uniform(values):
    values = {value for value in values if value}
    return values.pop() if len(values) == 1 else ("mixed" if values else "")


@event_write(permission=False)  # the caller (view, station cookie or lease) already authorised the write
def record_receipts(event, receipts, *, actor=None, method=None):
    """-> (recorded, duplicates). `receipts` are validated dicts: operation_id, registration_id, printed_at, and
    optionally method, stock and role. Rows for another event's registrations are ignored (never an error that
    reveals them); an operation id already recorded counts as a duplicate."""
    receipts = list(receipts)[:BATCH_MAX]
    known = set(EventBadgePrint.objects.filter(
        event=event, operation_id__in=[item["operation_id"] for item in receipts]).values_list("operation_id", flat=True))
    registrations = set(EventRegistration.objects.filter(
        event=event, pk__in=[item["registration_id"] for item in receipts]).values_list("pk", flat=True))
    cards = dict(EventIdCard.objects.filter(
        event=event, registration_id__in=registrations, status=EventIdCard.Status.ACTIVE).values_list(
        "registration_id", "pk"))
    fresh, seen = [], set()
    for item in receipts:
        operation_id = item["operation_id"]
        if operation_id in known or operation_id in seen:
            continue
        if item["registration_id"] not in registrations:
            continue
        seen.add(operation_id)
        fresh.append(EventBadgePrint(
            makerspace_id=event.makerspace_id, event=event, registration_id=item["registration_id"],
            card_id=cards.get(item["registration_id"]), actor=actor,
            method=method or item.get("method") or EventBadgePrint.Method.DESK, stock=(item.get("stock") or "")[:32],
            role=(item.get("role") or "")[:12], operation_id=operation_id,
            printed_at=item.get("printed_at") or timezone.now()))
    if fresh:
        EventBadgePrint.objects.bulk_create(fresh)
        audit.record(actor, "event_badge.printed", makerspace=event.makerspace, target=event,
                     meta={"count": len(fresh), "method": _uniform(row.method for row in fresh),
                           "stock": _uniform(row.stock for row in fresh), "role": _uniform(row.role for row in fresh)})
    return len(fresh), len(receipts) - len(fresh)


def record_bulk(event, actor, card_ids):
    """A bulk job prints these cards: one receipt each (called once, when the job is first queued)."""
    from uuid import uuid4
    rows = EventIdCard.objects.filter(event=event, pk__in=card_ids).values("pk", "registration_id", "role")
    receipts = [{"operation_id": uuid4(), "registration_id": row["registration_id"], "role": row["role"]}
                for row in rows]
    for start in range(0, len(receipts), BATCH_MAX):
        record_receipts(event, receipts[start:start + BATCH_MAX], actor=actor, method=EventBadgePrint.Method.BULK)
