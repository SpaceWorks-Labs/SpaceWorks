"""The "at risk" flag on a machine job (#142 OQ-6; GAP2 M3).

The member's "needed by" date is a hint, never a promise: it does NOT reorder the queue
(automatic deadline ordering invites gaming). Staff see a flag instead, with the reasons:

* ``needed_by_passed`` -- the date is already behind the space's local today;
* ``eta_after_needed_by`` -- the queue forecast finishes after that day ends;
* ``needed_by_soon`` -- there is no forecast (no estimate, no machine) and the date is today
  or tomorrow, and the job has not started.

Only open jobs carry a flag (review, waiting on the member, queued, running); a finished,
collected, rejected, failed or cancelled job never does. Pure: the caller passes the ETA
payload of the response's one queue snapshot and the space's local today.
"""

from datetime import datetime, timedelta

from django.utils.dateparse import parse_datetime

from apps.makerspaces.local_time import to_local

PASSED, LATE, SOON = "needed_by_passed", "eta_after_needed_by", "needed_by_soon"
REASONS = (PASSED, LATE, SOON)
OPEN = ("pending", "changes_requested", "quoted", "accepted", "in_progress")
SOON_DAYS = 1


def _finish(eta):
    value = (eta or {}).get("estimated_finish_at")
    if isinstance(value, str):
        value = parse_datetime(value)
    return value if isinstance(value, datetime) else None


def reasons(row, eta, today, makerspace):
    """Why `row` may miss its "needed by" date; empty when it is on track or has none."""
    if row.status not in OPEN or row.needed_by is None:
        return []
    if row.needed_by < today:
        return [PASSED]
    finish = _finish(eta)
    if finish is not None:
        return [LATE] if to_local(makerspace, finish).date() > row.needed_by else []
    if row.status != "in_progress" and row.needed_by <= today + timedelta(days=SOON_DAYS):
        return [SOON]
    return []


def for_serializer(serializer, row, eta):
    """Serializer helper: one local "today" per makerspace per response (no per-row query)."""
    if row.status not in OPEN or row.needed_by is None:
        return []
    cache = serializer.context.setdefault("_job_risk_spaces", {})
    if row.makerspace_id not in cache:
        from apps.makerspaces.local_time import local_now
        space = row.makerspace
        cache[row.makerspace_id] = (space, local_now(space).date())
    space, today = cache[row.makerspace_id]
    return reasons(row, eta, today, space)
