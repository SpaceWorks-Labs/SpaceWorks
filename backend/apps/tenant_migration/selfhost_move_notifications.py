"""Who hears about a self-host move (release 2 L11).

* A new request -> the superadmins, by platform email (they run the move in /control/).
* Every status change -> the space's Space Managers: a console notice in the space's feed
  and an email through the notification outbox (the Space-Manager technical category,
  like a finished restore). The notice never carries the archive, a link to it or the
  key: the Space Manager has no download surface (#111 Q2).
Delivery failure never fails the move; the audit row is the durable record.
"""
from config.locale_resolution import override_for
from django.utils.translation import gettext, gettext_noop
from apps.accounts import rbac
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.operations.notifications_p2 import body, fanout, revision, safe_notification, staff_link

SOURCE = "tenant_migration.selfhost_move"
EVENT = "selfhost_move_status"
TEXT = {
    "requested": gettext_noop("Your request to move {name} to its own server was sent. The platform operator reviews it."),
    "approved": gettext_noop("The platform operator approved moving {name} to its own server and will run the export."),
    "rejected": gettext_noop("The platform operator declined the request to move {name} to its own server."),
    "exporting": gettext_noop("The export of {name} for its new server is running."),
    "exported": gettext_noop("{name} was exported for its new server. The platform operator hands it to the new "
                             "server's operator; staff and members keep their sign-in there."),
    "failed": gettext_noop("The export of {name} for its new server did not complete. The platform operator will retry."),
}


def _load(envelope):
    from .models_selfhost_move import SelfHostMoveRequest
    return SelfHostMoveRequest.objects.select_related("makerspace").filter(
        pk=envelope.source_id, makerspace_id=envelope.makerspace_id).first()


def source_revision(move):
    return revision(move.pk, move.status, move.updated_at)


def eligible(envelope):
    move = _load(envelope)
    return bool(move and envelope.event == EVENT and envelope.audience == "staff"
                and envelope.revision == source_revision(move)
                and rbac.can(envelope.recipient, rbac.Action.MANAGE_MAKERSPACE, move.makerspace_id))


def content(move):
    name = move.makerspace.name
    text = gettext(TEXT.get(move.status, gettext_noop("The move of {name} to its own server changed."))).format(name=name)
    return body(gettext("Moving %(name)s to its own server: %(status)s") % {
        "name": name, "status": move.get_status_display().lower()}, text,
                staff_link(move.makerspace, "settings"))


def render(envelope):
    return content(_load(envelope))


@safe_notification
def _email(move):
    return fanout(row=move, space=move.makerspace, feature="api_access", stream="makerspace", event=EVENT,
                  source_kind=SOURCE, revision=source_revision(move), staff_body=lambda: content(move), rooms=False)


def notify_status(move):
    from apps.notifications.models import Notification
    with override_for(makerspace=move.makerspace):  # a makerspace-wide row has no recipient
        message = content(move)
    try:
        Notification.objects.create(
            makerspace=move.makerspace, event=f"tenant_migration.{EVENT}",
            level=Notification.Level.CRITICAL if move.status == "failed" else Notification.Level.INFO,
            title=message["subject"][:200], body=message["text"], url_path=message["link"][:300])
    except Exception:  # the notifications app may be tombstoned; the audit row remains
        pass
    _email(move)


def notify_requested(move):
    from apps.backup.operator_notice import notify_superadmins
    note = f"\n\nTheir note: {move.note}" if move.note else ""
    notify_superadmins(f"Self-host move requested: {move.makerspace.name}",
                       f"A Space Manager of {move.makerspace.name} asked to move the space to its own server. "
                       f"Review it under Self-host move requests in the control plane.{note}",
                       event="selfhost_move_requested")


def register():
    register_source(SOURCE, NotificationSource(eligible, render))
