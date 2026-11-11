"""Tell a space's managers about an emergency re-key (#120, #128 C-26).

Two channels, like a per-space restore outcome: a console notice in the space's feed
(which the superadmin also sees, #115) and an email to the space's Space Managers through
the outbox. Delivery failure never fails the re-key: the audit row is the durable record.
"""

from django.utils.translation import gettext
from config.locale_resolution import override_for
from apps.accounts import rbac
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.operations.notifications_p2 import body, fanout, revision, safe_notification, staff_link

SOURCE = "encryption.key_job"
EVENTS = {"running": "emergency_rekey_started", "completed": "emergency_rekey_completed",
          "failed": "emergency_rekey_failed"}


def _load(envelope):
    from .models_rotation import KeyRotationJob
    return KeyRotationJob.objects.select_related("makerspace").filter(
        pk=envelope.source_id, makerspace_id=envelope.makerspace_id).first()


def source_revision(job):
    return revision(job.pk, job.status, job.completed_at)


def eligible(envelope):
    job = _load(envelope)
    return bool(job and EVENTS.get(job.status) == envelope.event and envelope.audience == "staff"
                and envelope.revision == source_revision(job)
                and rbac.can(envelope.recipient, rbac.Action.MANAGE_MAKERSPACE, job.makerspace_id))


def content(job):
    space = job.makerspace
    link = staff_link(space, "security")
    if job.status == "running":
        return body(gettext("%(space)s's encryption key was replaced") % {"space": space.name},
                    gettext("The platform started an emergency re-key of %(space)s: new data is already protected "
                            "by key version %(version)s, and existing records are being re-encrypted in the "
                            "background.") % {"space": space.name, "version": job.to_version},
                    link)
    if job.status == "completed":
        return body(gettext("Emergency re-key of %(space)s finished") % {"space": space.name},
                    gettext("Every record of %(space)s that can be rewritten now uses key version %(version)s.")
                    % {"space": space.name, "version": job.to_version},
                    link)
    return body(gettext("Emergency re-key of %(space)s needs attention") % {"space": space.name},
                gettext("New data uses key version %(version)s, but re-encrypting older records stopped "
                        "(%(code)s). The platform team has been told.")
                % {"version": job.to_version, "code": job.error_code}, link)


def render(envelope):
    return content(_load(envelope))


@safe_notification
def _email(job):
    return fanout(row=job, space=job.makerspace, feature="api_access", stream="makerspace",
                  event=EVENTS[job.status], source_kind=SOURCE, revision=source_revision(job),
                  staff_body=lambda: content(job), rooms=False)


def notify(job):
    from apps.notifications.models import Notification
    with override_for(makerspace=job.makerspace):  # a makerspace-wide row has no recipient
        message = content(job)
    Notification.objects.create(
        makerspace=job.makerspace, event=f"encryption.{EVENTS[job.status]}",
        level=Notification.Level.INFO if job.status == "completed" else Notification.Level.CRITICAL,
        title=message["subject"][:200], body=message["text"], url_path=message["link"][:300],
    )
    _email(job)


def register():
    register_source(SOURCE, NotificationSource(eligible, render))
