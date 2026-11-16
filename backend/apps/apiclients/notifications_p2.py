"""API request outcomes contain navigation, never client secrets."""
from django.utils.translation import gettext

from apps.integrations.notification_links import local_link
from apps.accounts import rbac
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.operations.notifications_p2 import body, fanout, revision, safe_notification, scoped, staff_link
from .models import ApiKeyRequest

SOURCE = "apiclients.request"


def source_revision(row):
    return revision(row.pk, row.status, row.resolved_at, row.updated_at)


def load(envelope):
    return scoped(ApiKeyRequest, envelope.makerspace_id).select_related(
        "makerspace", "requester", "resolved_by",
    ).filter(pk=envelope.source_id).first()


def eligible(envelope):
    row = load(envelope)
    return bool(row and row.status in {"approved", "rejected"}
        and envelope.event == "api_key_request_resolved"
        and envelope.revision == source_revision(row)
        and (envelope.audience == "staff" or row.requester_id == envelope.recipient_id)
        and row.resolved_by and rbac.can(row.resolved_by, rbac.Action.MANAGE_MAKERSPACE, row.makerspace_id))


def content(row, audience):
    if audience == "staff":
        return body(gettext("API access request resolved"),
                    gettext("API access request #%(id)s was %(status)s.") % {"id": row.pk, "status": row.status},
                    staff_link(row.makerspace, "api-access"))
    text = gettext("Your API access request '%(label)s' for %(space)s was %(status)s.") % {
        "label": row.label, "space": row.makerspace.name, "status": row.status}
    if row.resolution_note:
        text += "\n\n" + gettext("Note: %(note)s") % {"note": row.resolution_note}
    return body(gettext("%(space)s API access request %(status)s") % {"space": row.makerspace.name, "status": row.status},
                text + "\n\n" + gettext("No API secret is included in this notification."), local_link(row.makerspace, "member"))


def render(envelope):
    return content(load(envelope), envelope.audience)


@safe_notification
def notify_api_key_request_resolved(row, *, sync=False):
    return fanout(row=row, space=row.makerspace, feature="api_access", stream="api",
        event="api_key_request_resolved", source_kind=SOURCE, revision=source_revision(row),
        owner=row.requester, owner_body=lambda: content(row, "requester"), staff_body=lambda: content(row, "staff"))


def register():
    register_source(SOURCE, NotificationSource(eligible, render))
