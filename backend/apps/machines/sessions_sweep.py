"""Forgot to stop (#158.5): the sweep that ends live sessions nobody stopped.

A live member/staff session stops itself at the EARLIEST of:

* its type's `session_max_minutes` after the start (default 240);
* the member's check-out -- their presence session ended or expired (only while the
  `presence` module is on: without check-in there is no check-out);
* the space's closing time, from the opening hours the job ETA uses (a space with no
  hours recorded never closes).

The session ends at that moment (not when the sweep happens to run), so the time billed
is the time the machine could have been in use. Auto-stopped sessions are FLAGGED and
held for staff to check and confirm. Device sessions are closed by the machine's own
reports, never here. Bounded per tick; every row runs in its own tenant boundary.
"""

import logging
from datetime import timedelta

from django.utils import timezone

from apps.accounts import rbac

logger = logging.getLogger(__name__)
LIMIT = 200
LABEL = "machine-sessions"


def _check_out(session, now):
    from apps.makerspaces.platform import module_enabled
    from apps.presence.models import PresenceSession
    from apps.separability.registry import runtime_active
    if not runtime_active("presence") or not module_enabled(session.makerspace, "presence"):
        return None
    latest = PresenceSession.objects.filter(member_id=session.member_id, makerspace_id=session.makerspace_id,
                                            started_at__lte=now).order_by("-started_at", "-pk").first()
    if latest is None:
        return None
    if latest.ended_at is not None:
        return latest.ended_at
    return latest.expires_at if latest.expires_at <= now else None


def due_stop(session, now=None):
    """`(reason, at)` for the earliest auto-stop that is due by `now`, else None."""
    from apps.machines.job_policy import policy_for
    from apps.makerspaces.opening_hours import closing_time
    now = now or timezone.now()
    limit = policy_for(session.makerspace, session.machine_type).session_max_minutes or 240
    candidates = [("max_length", session.started_at + timedelta(minutes=limit))]
    checked_out = _check_out(session, now)
    if checked_out is not None:
        candidates.append(("check_out", max(checked_out, session.started_at)))
    closes = closing_time(session.makerspace, session.started_at)
    if closes is not None:
        candidates.append(("closing", closes))
    reason, at = min(candidates, key=lambda pair: pair[1])
    return (reason, at) if at <= now else None


def _rows():
    from apps.machines.models import MachineSession
    from apps.machines.sessions_state import FEATURE
    rows = MachineSession.objects.filter(ended_at__isnull=True, makerspace__enabled_features__contains=[FEATURE]) \
        .exclude(source=MachineSession.Source.DEVICE).select_related("makerspace", "machine", "machine_type")
    return rbac.scope_for_scheduled_work(rows).order_by("pk")[:LIMIT]


def run_session_sweep(*, now=None):
    from apps.machines.sessions_service import stop
    from apps.machines.sessions_state import sessions_on
    from apps.operations.cloud_jobs import bounded
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    now = now or timezone.now()
    counts = {"skipped": 0, "auto_stopped": 0}
    for row in bounded.page(_rows(), LABEL):
        with fanout_tenant_write(row.makerspace_id, operation="auto_stop", counts=counts) as go:
            if not go:
                continue
            if not sessions_on(row.makerspace):
                continue
            try:
                due = due_stop(row, now)
                if due is not None:
                    stop(row, actor=None, reason=due[0], at=due[1])
                    counts["auto_stopped"] += 1
            except Exception:
                counts["skipped"] += 1
                logger.exception("machine_session_sweep_failed", extra={"session_id": row.pk})
    return counts
