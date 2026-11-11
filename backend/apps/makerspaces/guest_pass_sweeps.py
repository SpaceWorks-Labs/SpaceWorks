"""Decision 223: the scheduled guest-pass work, run inside the hourly membership sweep.

`run_guest_pass_sweeps` is called by `tasks_membership.run_membership_renewals_task` (the same
piggyback decision 221(f) used for pickup reminders), so no new beat entry exists. For every
space with `membership.guest_passes` on, one tenant at a time inside the skip-and-count source-gate
boundary:

1. `expire_due_passes` -- flips ended passes to `expired` (reading never depends on this);
2. `send_expiring_notices` -- the "ends within the hour" notice to each holder;
3. `record_outstanding_at_pass_end` -- a sponsored guest who still holds items: incident + sponsor notice.
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)
FEATURE = "membership.guest_passes"


def run_guest_pass_sweeps(*, now=None):
    from apps.hardware_requests.guest_liability import record_outstanding_at_pass_end
    from apps.makerspaces.guest_pass_lifecycle import expire_due_passes
    from apps.makerspaces.notifications_guest_passes import send_expiring_notices
    from apps.makerspaces.scheduled_scope import live_space_ids
    from apps.makerspaces.servability import servable_queryset
    from apps.tenant_migration.gate_runtime import fanout_tenant_write

    now = now or timezone.now()
    counts = {"expired": 0, "notified": 0, "outstanding": 0, "skipped": 0, "failed": 0}
    for space in servable_queryset().filter(pk__in=live_space_ids(FEATURE)).order_by("pk"):
        with fanout_tenant_write(space.pk, operation="guest_pass_sweep", counts=counts) as go:
            if not go:
                continue
            try:
                counts["expired"] += expire_due_passes(space, now)
                counts["notified"] += send_expiring_notices(now, makerspace=space)
                counts["outstanding"] += record_outstanding_at_pass_end(now, makerspace=space)
            except Exception:
                counts["failed"] += 1
                logger.exception("guest_pass_sweep_failed", extra={"makerspace_id": space.pk})
    return counts
