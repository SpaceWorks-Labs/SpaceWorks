"""Trials (#187A): reminders before the end (7 and 1 days), read-only when it ends.

Read-only reuses #185's mode with ``source=trial_expired``; assigning a plan again lifts
only that source. Reminders are platform mail to the space's Space Managers.
"""

import math

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.space_controls.errors import SpaceControlConflict
from apps.space_controls.notifications import schedule_manager_mail

from .models import SpacePlanAssignment

REMINDER_DAYS = (7, 1)
EXPIRED_REASON = "The trial of this space has ended. Ask the platform operator to choose a plan."


def remind(row, now):
    days_left = math.ceil((row.trial_ends_at - now).total_seconds() / 86400)
    keys = [f"trial:{days}" for days in REMINDER_DAYS if days_left <= days and f"trial:{days}" not in row.reminders_sent]
    if not keys:
        return False
    space = row.makerspace
    plural = "day" if days_left == 1 else "days"
    schedule_manager_mail(space.pk, subject=f"{space.name}: your trial ends in {days_left} {plural}",
                          body=(f"The {row.plan.name} trial for {space.name} ends on "
                                f"{timezone.localtime(row.trial_ends_at):%Y-%m-%d}. After that the space becomes "
                                "read-only until a plan is chosen. Contact the platform operator to continue."),
                          event="managed_hosting_trial_reminder")
    row.reminders_sent = [*row.reminders_sent, *keys]
    row.save(update_fields=["reminders_sent"])
    return True


def expire(row, now):
    from apps.space_controls.models import SpaceControlState
    from apps.space_controls.services_access import set_read_only

    with transaction.atomic():
        locked = SpacePlanAssignment.objects.select_for_update().get(pk=row.pk)
        if locked.trial_expired_at is not None:
            return False
        locked.trial_expired_at = now
        locked.save(update_fields=["trial_expired_at"])
        audit.record(None, "managed_hosting.trial_expired", makerspace=locked.makerspace, target=locked.makerspace,
                     meta={"plan_id": locked.plan_id})
    try:
        set_read_only(None, row.makerspace_id, EXPIRED_REASON, source=SpaceControlState.ReadOnlySource.TRIAL_EXPIRED)
    except SpaceControlConflict:
        pass  # archived or importing: nothing to restrict
    return True


def sweep(now=None):
    now = now or timezone.now()
    counts = {"reminded": 0, "expired": 0}
    rows = SpacePlanAssignment.objects.select_related("makerspace", "plan").filter(
        trial_ends_at__isnull=False, trial_expired_at__isnull=True)
    for row in rows[:200]:
        if row.trial_ends_at <= now:
            counts["expired"] += int(expire(row, now))
        else:
            counts["reminded"] += int(remind(row, now))
    return counts
