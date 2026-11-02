"""Queue order (#142 OQ-5/OQ-6): urgent first, then the queue anchor, then id.

`queued_at` is the anchor (empty = the submission time): kept while the member answers a
change request or a quote within three days, else their answer time. A staff reorder moves one
job by giving it an anchor between its new neighbours, so position, ETA, the
"You're next" notice and the staff board keep reading ONE sort key.
"""

from datetime import timedelta

from django.db.models import Case, F, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import MachineServiceRequest

Status = MachineServiceRequest.Status


def anchor_expression():
    return Coalesce(F("queued_at"), F("created_at"))


def ordering():
    """Waiting rows: accepted before pending, urgent first, then the anchor and id."""
    accepted_first = Case(When(status=Status.ACCEPTED, then=Value(0)), default=Value(1))
    urgent_first = Case(When(urgent=True, then=Value(0)), default=Value(1))
    return (accepted_first, urgent_first, anchor_expression(), "id")


def order_key(urgent, queued_at, created_at):
    """The Python twin of `ordering()` for in-memory records (the ETA simulator)."""
    return (0 if urgent else 1, queued_at or created_at)


def answered_anchor(row, waited_since, *, now=None):
    """OQ-5: keep the place if the member answered within the window, else move it."""
    now = now or timezone.now()
    from .job_policy import KEEP_PLACE_DAYS
    if waited_since is not None and now - waited_since > timedelta(days=KEEP_PLACE_DAYS):
        return now
    return row.queued_at or row.created_at


def scope_rows(row):
    scope = {"queue_id": row.queue_id} if row.queue_id else {"bucket_id": row.bucket_id}
    return MachineServiceRequest.objects.filter(makerspace_id=row.makerspace_id, status=Status.ACCEPTED, **scope)


def anchor_for_position(row, position):
    """The anchor that puts `row` at 1-based `position` among its scope's same-urgency jobs."""
    peers = list(scope_rows(row).filter(urgent=row.urgent).exclude(pk=row.pk)
                 .annotate(anchor=anchor_expression()).order_by("anchor", "id").values_list("anchor", flat=True))
    index = max(0, min(int(position) - 1, len(peers)))
    before = peers[index - 1] if index > 0 else None
    after = peers[index] if index < len(peers) else None
    if before is None and after is None:
        return row.queued_at or row.created_at
    if before is None:
        return after - timedelta(seconds=1)
    if after is None:
        return before + timedelta(seconds=1)
    middle = before + (after - before) / 2
    # Equal neighbours leave no room: nudge by a microsecond, ties break on id.
    return middle if middle != before else before + timedelta(microseconds=1)
