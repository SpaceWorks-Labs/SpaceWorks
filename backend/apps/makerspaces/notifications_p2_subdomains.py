"""Technical-access outcomes use the existing Space-Manager access category."""
from apps.accounts import rbac
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.operations.notifications_p2 import body, fanout, revision, safe_notification, scoped, staff_link
from .models import SubdomainRequest

SOURCE = "makerspaces.subdomain"


def source_revision(row):
    return revision(row.pk, row.status, row.decided_at, row.updated_at)


def load(envelope):
    return scoped(SubdomainRequest, envelope.makerspace_id).select_related(
        "makerspace", "requested_by", "decided_by",
    ).filter(pk=envelope.source_id).first()


def eligible(envelope):
    row = load(envelope)
    return bool(row and row.status in {"approved", "rejected"}
        and envelope.event == "subdomain_request_resolved" and envelope.revision == source_revision(row)
        and (envelope.audience == "staff" or row.requested_by_id == envelope.recipient_id)
        and row.decided_by and rbac.can(row.decided_by, rbac.Action.MANAGE_MAKERSPACE, row.makerspace_id))


def content(row, audience):
    if audience == "staff":
        return body("Subdomain request resolved", f"Subdomain request #{row.pk} was {row.status}.", staff_link(row.makerspace, "settings"))
    text = f"Your subdomain request '{row.requested_label}' for {row.makerspace.name} was {row.status}."
    if row.status == "approved":
        text += f"\n\nYour new address is {row.makerspace.frontend_domain}."
    elif row.note:
        text += f"\n\nNote: {row.note}"
    return body(f"{row.makerspace.name} subdomain request {row.status}", text, staff_link(row.makerspace, "settings"))


def render(envelope):
    return content(load(envelope), envelope.audience)


@safe_notification
def notify_subdomain_request_resolved(row):
    # Not the account stream: that stream is reserved for email-only proofs.
    return fanout(row=row, space=row.makerspace, feature="api_access", stream="makerspace",
        event="subdomain_request_resolved", source_kind=SOURCE, revision=source_revision(row),
        owner=row.requested_by, owner_body=content(row, "requester"), staff_body=content(row, "staff"))


def register():
    register_source(SOURCE, NotificationSource(eligible, render))
