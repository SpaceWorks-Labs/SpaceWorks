"""Observed progress never regresses; delivery evidence outranks failure."""
from apps.audit.services import record

RANKS = {"queued": 1, "accepted": 1, "sending": 1, "sent": 2, "delivered": 3, "read": 4}
TIMESTAMPS = {1: "accepted_at", 2: "sent_at", 3: "delivered_at", 4: "read_at"}


def derived_status(row):
    if row.progress_rank >= 3:
        return "read" if row.progress_rank == 4 else "delivered"
    if row.failed_at is not None or row.status == "failed":
        return "failed"
    return {2: "sent", 1: "accepted"}.get(row.progress_rank, row.status)


def observe(row, status, *, at=None, error_code="", billed_segments=None):
    rank = RANKS.get(status, 0)
    row.progress_rank = max(row.progress_rank, rank)
    if rank and at is not None and getattr(row, TIMESTAMPS[rank]) is None:
        setattr(row, TIMESTAMPS[rank], at)
    if status in {"failed", "undelivered"}:
        if at is not None and row.failed_at is None:
            row.failed_at = at
        # Missing provider timestamps remain NULL; status itself preserves failure.
        if row.progress_rank < 3:
            row.status = "failed"
        if error_code:
            row.error_code = error_code
    if billed_segments is not None:
        row.billed_segments = billed_segments
    row.status = derived_status(row)


def save_outcome(row, action="messaging.delivery_updated"):
    row.save()
    record(None, action, makerspace=row.makerspace, target=row,
           meta={"fields": ["status", "progress_rank", "skip_reason", "error_code"]})
