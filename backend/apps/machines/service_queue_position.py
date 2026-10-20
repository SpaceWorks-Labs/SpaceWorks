"""Canonical member-safe ranks for the machine-service waiting queue."""

from collections import defaultdict

from django.db.models import Case, Q, Value, When

from apps.machines.models import MachineServiceRequest


WAITING_STATUSES = (
    MachineServiceRequest.Status.PENDING,
    MachineServiceRequest.Status.ACCEPTED,
)


def queue_positions_for(requests) -> dict[int, int]:
    """Return positions within each bucket or pooled queue, accepted work first.

    Shares the one batched ranking query with ``queue_counts_for``: no per-scope query.
    """
    return {pk: counts["position"] for pk, counts in queue_counts_for(requests).items()}


def queue_counts_for(requests) -> dict[int, dict]:
    """Return queue counts with a bounded query count for a list of requests."""
    targets = [row for row in requests if row.status in WAITING_STATUSES]
    if not targets:
        return {}
    wanted = {row.pk for row in targets}
    counts = {}
    for ranked in _waiting_rows(_scope_keys(targets)).values():
        accepted = pending = 0
        for candidate in ranked:
            if candidate.pk in wanted:
                own_pending = candidate.status != MachineServiceRequest.Status.ACCEPTED
                counts[candidate.pk] = {
                    "position": accepted + pending + 1,
                    "approved_ahead": accepted,
                    "awaiting_review_ahead": pending if own_pending else 0,
                }
            if candidate.status == MachineServiceRequest.Status.ACCEPTED:
                accepted += 1
            else:
                pending += 1
    return {row.pk: counts[row.pk] for row in targets if row.pk in counts}


def _scope_key(row):
    return ("bucket", row.bucket_id) if row.bucket_id else ("queue", row.queue_id)


def _scope_keys(rows):
    return {_scope_key(row) for row in rows}


def _waiting_rows(keys):
    queue_ids = [value for field, value in keys if field == "queue"]
    bucket_ids = [value for field, value in keys if field == "bucket"]
    rows = MachineServiceRequest.objects.filter(status__in=WAITING_STATUSES).filter(
        Q(queue_id__in=queue_ids) | Q(bucket_id__in=bucket_ids),
    ).only("id", "status", "queue_id", "bucket_id", "created_at").order_by(_priority(), "created_at", "id")
    grouped = defaultdict(list)
    for row in rows:
        grouped[_scope_key(row)].append(row)
    return grouped


def _priority():
    return Case(
        When(status=MachineServiceRequest.Status.ACCEPTED, then=Value(0)),
        default=Value(1),
    )