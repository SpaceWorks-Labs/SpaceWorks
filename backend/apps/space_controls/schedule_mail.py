"""Mail and reminders for scheduled archive and purge (#185 item 4).

Reminders go to the space's Space Managers before the archive (7 and 1 days) and before
the purge (30, 7 and 1 days). When several thresholds are already past (a short grace
period), ONE mail is sent and every passed threshold is marked, so nobody gets three
mails at once. Keys live in ``SpaceControlState.reminders_sent`` and reset with the schedule.
"""

from django.utils.translation import gettext
import math

from django.utils import timezone

from .notifications import schedule_manager_mail

ARCHIVE_REMINDER_DAYS = (7, 1)
PURGE_REMINDER_DAYS = (30, 7, 1)


def _day(moment):
    return f"{timezone.localtime(moment):%Y-%m-%d %H:%M %Z}"


def schedule_set_mail(space, state):
    if state.archive_on:
        body = (f"The platform operator has scheduled {space.name} to be archived on {_day(state.archive_on)}.\n\n"
                f"After archiving, its data is kept for {state.purge_grace_days} days and then permanently deleted. "
                "Export anything you need before then. Contact the platform operator if this is a mistake.")
    else:
        body = (f"{space.name} is archived and is scheduled to be permanently deleted on {_day(state.purge_due_at)}.\n\n"
                "Contact the platform operator if you need anything from it before then.")
    schedule_manager_mail(space.pk, subject=gettext('{name}: archive and deletion scheduled').format(name=space.name), body=body,
                          event="space_control_schedule_set")


def schedule_cancelled_mail(space):
    schedule_manager_mail(space.pk, subject=gettext('{name}: scheduled archive cancelled').format(name=space.name),
                          body=f"The platform operator cancelled the scheduled archive or deletion of {space.name}.",
                          event="space_control_schedule_cancelled")


def archived_mail(space, state):
    schedule_manager_mail(space.pk, subject=gettext('{name} has been archived').format(name=space.name),
                          body=(f"{space.name} was archived as scheduled. Its data will be permanently deleted on "
                                f"{_day(state.purge_due_at)} unless the platform operator cancels it."),
                          event="space_control_scheduled_archive")


def due_reminder(state, now=None):
    """(kind, days_left, keys_to_mark) for the reminder this state owes now, else None."""
    now = now or timezone.now()
    if state.archive_on is not None:
        kind, moment, offsets = "archive", state.archive_on, ARCHIVE_REMINDER_DAYS
    elif state.purge_due_at is not None:
        kind, moment, offsets = "purge", state.purge_due_at, PURGE_REMINDER_DAYS
    else:
        return None
    if moment <= now:
        return None
    days_left = math.ceil((moment - now).total_seconds() / 86400)
    keys = [f"{kind}:{days}" for days in offsets
            if days_left <= days and f"{kind}:{days}" not in (state.reminders_sent or [])]
    return (kind, days_left, keys) if keys else None


def send_reminder(state, now=None):
    """Mail the owed reminder and record it; returns whether one was sent."""
    owed = due_reminder(state, now)
    if owed is None:
        return False
    kind, days_left, keys = owed
    space = state.makerspace
    when = "archived" if kind == "archive" else "permanently deleted"
    moment = state.archive_on if kind == "archive" else state.purge_due_at
    plural = "day" if days_left == 1 else "days"
    schedule_manager_mail(space.pk, subject=gettext('Reminder: {name} will be {when} in {days_left} {plural}').format(name=space.name, when=when, days_left=days_left, plural=plural),
                          body=(f"{space.name} will be {when} on {_day(moment)}.\n\n"
                                "Export anything you need before then. Contact the platform operator to cancel."),
                          event=f"space_control_{kind}_reminder")
    state.reminders_sent = [*(state.reminders_sent or []), *keys]
    state.save(update_fields=["reminders_sent", "updated_at"])
    return True
