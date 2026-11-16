"""`repair_closed`: the reporter's own "your problem was fixed" notice (decision 221(f)).

An account reporter hears through their own channels (an envelope under the repair area's
family: machines `maintenance`, items `hardware_requests`, rooms `bookings`) with their
preferences and quiet hours; an account-less reporter keeps the one direct email to the
address they gave. The copy names the subject and the issue title only -- never staff
notes, costs or a contractor. At send the issue must still be fixed or closed with the same
reporter, and the area's reporting or repairs switch must still be on.
"""

from apps.integrations.notification_links import local_link
from apps.operations.notifications_p2 import body, direct_mail_unless_routed, fanout, revision, safe_notification

from . import areas

SOURCE = "maintenance.repair_closed"
EVENT = "repair_closed"
DONE = ("fixed", "closed")


def _family(issue):
    from .notify import FAMILY
    return FAMILY[issue.area]


def _revision(issue):
    return revision(issue.pk, EVENT, issue.reporter_id)


def copy(issue):
    from .notify import subject_label
    return (f"Fixed: {issue.title}"[:200],
            f"Thanks for reporting a problem with {subject_label(issue)} at {issue.makerspace.name}.\n\n"
            f"It has been fixed. Issue #{issue.pk}: {issue.title}.")


@safe_notification
def notify_reporter(issue):
    """Queue the reporter's envelope, keeping the direct email unless their own channel emails it.

    Returns the outbox result, or None for a staff-filed issue or a reporter with no address
    and no account. An account-less reporter keeps the one direct email to the address given.
    """
    if issue.source == "staff" or not (issue.reporter_id or issue.reporter_email):
        return None
    feature, stream = _family(issue)
    space, (subject, text) = issue.makerspace, copy(issue)
    version, owner = _revision(issue), issue.reporter
    result = fanout(row=issue, space=space, feature=feature, stream=stream, event=EVENT, source_kind=SOURCE,
                    revision=version, owner=owner, staff=False, rooms=False,
                    owner_body=body(subject, text, local_link(space, "member")) if owner else None,
                    context={"issue_id": issue.pk, "area": issue.area})
    address = (owner.email if owner else "") or issue.reporter_email
    direct_mail_unless_routed(space=space, source_kind=SOURCE, row=issue, revision=version, event=EVENT, owner=owner,
                              to_email=address, subject=subject, text=text, stream="maintenance",
                              audience="requester", feature=feature, address_owner=False)
    return result if address or owner else None


def eligible(envelope):
    from apps.accounts import rbac
    from apps.maintenance.models import IssueReport
    issue = rbac.scope_notification_policy(IssueReport.objects.all(), makerspace_id=envelope.makerspace_id).filter(
        pk=envelope.source_id).select_related("makerspace").first()
    return bool(issue and envelope.event == EVENT and envelope.audience == "requester"
                and issue.state in DONE and issue.reporter_id == envelope.recipient_id
                and _revision(issue) == envelope.revision and areas.area_on(issue.makerspace, issue.area))


def register():
    from apps.integrations.notification_sources import NotificationSource, register_source
    register_source(SOURCE, NotificationSource(eligible))
