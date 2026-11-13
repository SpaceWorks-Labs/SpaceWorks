"""Mail and reminders for scheduled archive and purge (#185 item 4).

Reminders go to the space's Space Managers before the archive (7 and 1 days) and before
the purge (30, 7 and 1 days). When several thresholds are already past (a short grace
period), ONE mail is sent and every passed threshold is marked, so nobody gets three
mails at once. Keys live in ``SpaceControlState.reminders_sent`` and reset with the schedule.
"""

from django.utils.translation import gettext, ngettext
import math

from django.utils import timezone

from .notifications import schedule_manager_mail

ARCHIVE_REMINDER_DAYS = (7, 1)
PURGE_REMINDER_DAYS = (30, 7, 1)


def _day(moment):
    return f"{timezone.localtime(moment):%Y-%m-%d %H:%M %Z}"


def schedule_set_mail(space, state):
    name = space.name
    if state.archive_on:
        when, days = _day(state.archive_on), state.purge_grace_days

        def body():
            return gettext(
                "The platform operator has scheduled %(name)s to be archived on %(when)s.\n\n"
                "After archiving, its data is kept for %(days)s days and then permanently deleted. "
                "Export anything you need before then. Contact the platform operator if this is a mistake."
            ) % {"name": name, "when": when, "days": days}
    else:
        when = _day(state.purge_due_at)

        def body():
            return gettext(
                "%(name)s is archived and is scheduled to be permanently deleted on %(when)s.\n\n"
                "Contact the platform operator if you need anything from it before then."
            ) % {"name": name, "when": when}
    schedule_manager_mail(space.pk, subject=lambda: gettext("%(name)s: archive and deletion scheduled") % {"name": name},
                          body=body, event="space_control_schedule_set")


def schedule_cancelled_mail(space):
    name = space.name
    schedule_manager_mail(space.pk, subject=lambda: gettext("%(name)s: scheduled archive cancelled") % {"name": name},
                          body=lambda: gettext(
                              "The platform operator cancelled the scheduled archive or deletion of %(name)s."
                          ) % {"name": name},
                          event="space_control_schedule_cancelled")


def archived_mail(space, state):
    name, when = space.name, _day(state.purge_due_at)
    schedule_manager_mail(space.pk, subject=lambda: gettext("%(name)s has been archived") % {"name": name},
                          body=lambda: gettext(
                              "%(name)s was archived as scheduled. Its data will be permanently deleted on "
                              "%(when)s unless the platform operator cancels it."
                          ) % {"name": name, "when": when},
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
    name, archive = space.name, kind == "archive"
    moment = state.archive_on if archive else state.purge_due_at
    when_day = _day(moment)

    def subject():
        text = (ngettext("Reminder: %(name)s will be archived in %(days)s day",
                         "Reminder: %(name)s will be archived in %(days)s days", days_left) if archive else
                ngettext("Reminder: %(name)s will be permanently deleted in %(days)s day",
                         "Reminder: %(name)s will be permanently deleted in %(days)s days", days_left))
        return text % {"name": name, "days": days_left}

    def body():
        text = (gettext("%(name)s will be archived on %(when)s.") if archive
                else gettext("%(name)s will be permanently deleted on %(when)s."))
        return (text % {"name": name, "when": when_day} + "\n\n"
                + gettext("Export anything you need before then. Contact the platform operator to cancel."))

    schedule_manager_mail(space.pk, subject=subject, body=body, event=f"space_control_{kind}_reminder")
    state.reminders_sent = [*(state.reminders_sent or []), *keys]
    state.save(update_fields=["reminders_sent", "updated_at"])
    return True
