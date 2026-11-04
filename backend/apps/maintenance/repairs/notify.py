"""Who hears about an issue, and how (#103, #93; fail safe, never blocking a workflow).

* A new report, and a quote waiting for approval, reach that area's manager and the
  Space Manager through their own notification channels: machines through the
  `maintenance` family (scoped to the machine type), items through `hardware_requests`
  (the Inventory Manager's family), rooms through `bookings`.
* The reporter gets a plain "fixed" email (members and account-less borrowers alike).
* Bookers inside a room outage get an email naming the room and the window.

Bodies carry ids, the subject's name and the issue title -- never a reporter's or a
contractor's contact details.
"""

import logging

from apps.accounts import rbac
from apps.hardware_requests.notifications_p2 import fanout, revision, safe_adapter
from apps.integrations.destinations import NotificationScope
from apps.integrations.notification_sources import NotificationSource, register_source

from . import areas

logger = logging.getLogger(__name__)
KIND = "maintenance.issue_report"
FAMILY = {areas.MACHINES: ("maintenance", "maintenance"), areas.INVENTORY: ("hardware_requests", "hardware"),
          areas.ROOMS: ("bookings", "bookings")}
STAFF_EVENTS = ("issue_reported", "repair_quote_pending")


def subject_label(issue):
    subject = issue.subject
    return getattr(subject, "name", "") or getattr(subject, "asset_tag", "") or str(subject)


def version(issue, event):
    return revision(issue.pk, event, issue.state, issue.quote_state, issue.updated_at)


def eligible(envelope):
    from apps.maintenance.models import IssueReport
    row = rbac.scope_notification_policy(IssueReport.objects.all(), makerspace_id=envelope.makerspace_id).filter(
        pk=envelope.source_id).first()
    if row is None or envelope.audience != "staff" or envelope.event not in STAFF_EVENTS:
        return False
    if version(row, envelope.event) != envelope.revision or not areas.area_on(envelope.makerspace, row.area):
        return False
    if envelope.event == "repair_quote_pending" and row.quote_state != row.QuoteState.PENDING:
        return False
    return row.state in IssueReport.OPEN_STATES


@safe_adapter
def staff(issue, event):
    feature, stream = FAMILY[issue.area]
    label = subject_label(issue)
    if event == "issue_reported":
        text = f"Issue #{issue.pk} reported on {label}: {issue.title}. Review it in the staff console."
        title = "Issue reported"
    else:
        text = f"A repair quote on issue #{issue.pk} ({label}) is waiting for your approval."
        title = "Repair quote awaiting approval"
    scope = NotificationScope(machine=issue.machine) if issue.machine_id else None
    return fanout(space=issue.makerspace, feature=feature, stream=stream, event=event, kind=KIND,
                  source=issue.pk, version=version(issue, event), subject=issue, scope=scope,
                  staff={"subject": title, "text": text},
                  context={"issue_id": issue.pk, "area": issue.area},
                  staff_context={"issue_id": issue.pk})


def _email(space, to, subject, body, *, event, feature, recipient_id=None):
    from apps.integrations.email import send_makerspace_email
    try:
        return send_makerspace_email(space, subject, body, [to], stream="maintenance", event=event,
                                     audience="requester", recipient_id=recipient_id, feature=feature)
    except Exception as exc:  # outbound mail never breaks the workflow
        logger.warning("repairs_email_failed", extra={"makerspace_id": space.pk, "event": event,
                                                      "error_class": type(exc).__name__})
        return 0


def reporter_fixed(issue):
    """The reporter's own notice (#103). Returns whether a mail was queued."""
    address = (issue.reporter.email if issue.reporter_id and issue.reporter else "") or issue.reporter_email
    if not address:
        return False
    body = (f"Thanks for reporting a problem with {subject_label(issue)} at {issue.makerspace.name}.\n\n"
            f"It has been fixed. Issue #{issue.pk}: {issue.title}.")
    return bool(_email(issue.makerspace, address, f"Fixed: {issue.title}"[:200], body,
                       event="repair_fixed", feature="maintenance"))


def bookers_outage(outage, bookings):
    """Each affected booker hears the room is out of service; staff decide on each booking."""
    room = outage.room
    sent = 0
    for booking in bookings:
        if not booking.email:
            continue
        back = f" It is expected back {outage.expected_back_at:%Y-%m-%d %H:%M}." if outage.expected_back_at else ""
        body = (f"{room.name} at {outage.makerspace.name} is out of service.{back}\n\n"
                f"Your booking #{booking.pk} falls in this time. The space will contact you about it.")
        sent += _email(outage.makerspace, booking.email, f"{room.name} is out of service"[:200], body,
                       event="room_outage", feature="bookings", recipient_id=booking.member_id)
    return sent


def register():
    register_source(KIND, NotificationSource(eligible))
