"""Tell a space's managers how its restore ended (owner decision #111 Q15).

Two channels: a console notice in the space's notification feed, and an email to the
space's Space Managers through the notification outbox (the Space-Manager technical
access category, like a resolved subdomain request). Delivery failure never fails the
restore: the audit row is the durable record.
"""

from config.locale_resolution import override_for
from django.utils.translation import gettext
from apps.accounts import rbac
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.operations.notifications_p2 import body, fanout, revision, safe_notification, staff_link

SOURCE = "backup.space_restore"
EVENTS = {"completed": "space_restore_completed", "failed": "space_restore_failed"}


def _load(envelope):
    from .models import MakerspaceRestoreOperation
    return MakerspaceRestoreOperation.objects.select_related("makerspace").filter(
        pk=envelope.source_id, makerspace_id=envelope.makerspace_id).first()


def source_revision(op):
    return revision(op.pk, op.stage, op.finished_at)


def eligible(envelope):
    op = _load(envelope)
    return bool(op and EVENTS.get(op.stage) == envelope.event and envelope.audience == "staff"
                and envelope.revision == source_revision(op)
                and rbac.can(envelope.recipient, rbac.Action.MANAGE_MAKERSPACE, op.makerspace_id))


def content(op):
    space = op.makerspace
    if op.stage == "completed":
        report = op.report or {}
        flagged = len(report.get("money_after_restore_point", []))
        text = (gettext("%(space)s was restored to its backup from %(when)s UTC. "
                        "A safety backup of the space as it was is kept as a restore point.")
                % {"space": space.name, "when": f"{op.snapshot_at:%Y-%m-%d %H:%M}"})
        if flagged:
            text += " " + gettext("%(count)s payment record(s) made after the restore point were kept; review them.") % {
                "count": flagged}
        return body(gettext("%(space)s was restored from a backup") % {"space": space.name}, text,
                    staff_link(space, "backup"))
    return body(gettext("Restoring %(space)s failed") % {"space": space.name},
                gettext("The restore of %(space)s did not complete and nothing was changed. (%(code)s)")
                % {"space": space.name, "code": op.error_code},
                staff_link(space, "backup"))


def render(envelope):
    return content(_load(envelope))


@safe_notification
def _email(op):
    return fanout(row=op, space=op.makerspace, feature="api_access", stream="makerspace",
                  event=EVENTS[op.stage], source_kind=SOURCE, revision=source_revision(op),
                  staff_body=lambda: content(op), rooms=False)


def notify_outcome(op):
    from apps.notifications.models import Notification
    with override_for(makerspace=op.makerspace):  # a makerspace-wide row has no recipient
        message = content(op)
    Notification.objects.create(
        makerspace=op.makerspace, event=f"backup.{EVENTS[op.stage]}",
        level=Notification.Level.INFO if op.stage == "completed" else Notification.Level.CRITICAL,
        title=message["subject"][:200], body=message["text"], url_path=message["link"][:300],
    )
    _email(op)


def register():
    register_source(SOURCE, NotificationSource(eligible, render))
