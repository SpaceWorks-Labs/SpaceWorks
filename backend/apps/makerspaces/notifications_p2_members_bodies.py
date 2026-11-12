"""Owner and staff copy for membership lifecycle and application notices.

Split out of `notifications_p2_members.py` (300-line ceiling), which re-exports both builders.
"""
from django.utils.translation import gettext

from apps.integrations.email_templates_fablab import membership_context
from apps.integrations.email_templates_registry_helpers import bag
from apps.integrations.notification_links import local_link
from apps.operations.notifications_p2 import body, staff_link, template

# The member account portal's invitations section (frontend MemberArea `section=invitations`).
INVITATIONS_TAIL = "account-portal?section=invitations"


def member_body(row, event, audience):
    link = local_link(row.makerspace, "member")
    if audience == "staff":
        if event == "member_joined":
            return template(row.makerspace, "membership", audience, event,
                membership_context(row.makerspace, event, user=row.user), link=staff_link(row.makerspace, "members"))
        if event == "approved":
            return template(row.makerspace, "membership", audience, event,
                {"makerspace": bag(name=row.makerspace.name), "event_name": event,
                 "subject": bag(id=row.pk, status=row.status)}, link=staff_link(row.makerspace, "members"))
        return body(gettext("Membership update"), gettext("Membership #%(id)s: %(what)s.") % {
            "id": row.pk, "what": event.replace("_", " ")}, staff_link(row.makerspace, "members"))
    if event in {"approved", "joined"}:
        name = {"name": row.makerspace.name}
        return body(gettext("Welcome to %(name)s") % name,
                    gettext("Your membership at %(name)s is active. Welcome!") % name, link)
    if event == "verified":
        name = {"name": row.makerspace.name}
        return body(gettext("You are verified at %(name)s") % name,
                    gettext("You have been verified as a member of %(name)s.") % name, link)
    return body(gettext("Membership update"), gettext("Your membership at %(name)s: %(what)s.") % {
        "name": row.makerspace.name, "what": event.replace("_", " ")}, link)


def request_body(row, event, audience):
    if event == "request_pending":
        return template(row.makerspace, "membership", audience, event,
            membership_context(row.makerspace, event, request=row),
            link=staff_link(row.makerspace, "members") if audience == "staff" else local_link(row.makerspace, "member"))
    if event in {"declined", "awaiting_payment", "payment_due"}:
        return template(row.makerspace, "membership", audience, event,
            {"makerspace": bag(name=row.makerspace.name), "event_name": event,
             "subject": bag(id=row.pk, status=row.state)},
            link=staff_link(row.makerspace, "members") if audience == "staff" else local_link(row.makerspace, "member"))
    if event in ("changes_requested", "resubmitted"):  # parity O-B2
        from .notifications_p2_members_changes import changes_body
        return changes_body(row, event)
    if audience == "staff":
        return body(gettext("Membership application update"), gettext("Membership application #%(id)s: %(what)s.") % {
            "id": row.pk, "what": event.replace("_", " ")}, staff_link(row.makerspace, "members"))
    if event == "invitation":
        return body(gettext("Membership update"),
                    gettext("You have been invited to join this makerspace. Sign in to review the invitation."),
                    local_link(row.makerspace, "member", INVITATIONS_TAIL))
    text = gettext("Your membership application at %(name)s: %(what)s.") % {
        "name": row.makerspace.name, "what": event.replace("_", " ")}
    return body(gettext("Membership update"), text, local_link(row.makerspace, "member"))
