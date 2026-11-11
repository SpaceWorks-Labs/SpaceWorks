"""Parity O-B2: the two join-funnel notices -- an application sent back for changes (to the applicant) and its
resubmission (to staff). Called from `notifications_p2_members.request_body`."""
from django.utils.translation import gettext

from apps.integrations.notification_links import local_link
from apps.operations.notifications_p2 import body, staff_link


def changes_body(row, event):
    if event == "changes_requested":
        text = gettext("Please update your membership application at %(name)s and send it again.") % {
            "name": row.makerspace.name}
        if row.changes_note:
            text += "\n\n" + gettext("Note from the team: %(note)s") % {"note": row.changes_note}
        return body(gettext("Changes needed on your application"), text, local_link(row.makerspace, "member"))
    return body(gettext("Application resubmitted"), gettext(
        "Membership application #%(id)s was updated by the applicant and is waiting for review.") % {"id": row.pk},
        staff_link(row.makerspace, "members"))
