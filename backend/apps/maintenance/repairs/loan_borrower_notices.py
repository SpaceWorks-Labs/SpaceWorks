"""The borrower's repair update on a loan handoff (decisions 221(c), 221(f)).

An account borrower hears through their own channels (preferences, quiet hours) as a
`repair_closed` envelope under the repair area's family; an account-less borrower keeps
one direct email to the address on the loan. Copy names the item and loan only -- never
staff notes, costs or a contractor. When the borrower is also the reporter of a fixed issue
the reporter's own `repair_closed` notice already covers them, so nothing is sent twice.
"""

from apps.integrations.notification_links import local_link
from apps.operations.notifications_p2 import body, direct_mail_unless_routed, fanout, revision, safe_notification

from .repair_closed_notices import EVENT

SOURCE = "maintenance.repair_borrower"
OUTCOMES = ("fixed", "rejected")


def _revision(issue, outcome, owner_id):
    return revision(issue.pk, EVENT, outcome, owner_id)


def copy(issue, loan, outcome):
    from .notify import subject_label
    what = "has been repaired" if outcome == "fixed" else "was closed without a repair"
    return (f"Repair update: {subject_label(issue)}"[:200],
            f"The item you returned damaged on loan #{loan.pk} at {issue.makerspace.name} "
            f"({subject_label(issue)}) {what}.")


def _loan(issue):
    from apps.hardware_requests.models import HardwareRequest
    if not issue.return_line_id or not issue.loan_id:
        return None
    return HardwareRequest.objects.filter(pk=issue.loan_id, makerspace_id=issue.makerspace_id).select_related(
        "requester").first()


@safe_notification
def notify_borrower(issue, outcome):
    """Queue the borrower's notice. Returns the outbox result, or None when nobody is told."""
    loan = _loan(issue)
    if loan is None or outcome not in OUTCOMES:
        return None
    from apps.accounts.principal_guards import is_anonymous_requester
    owner = loan.requester if loan.requester_id and not is_anonymous_requester(loan.requester) else None
    address = (owner.email if owner else "") or loan.requester_contact_email
    if outcome == "fixed" and issue.source != "staff":
        if (owner and issue.reporter_id == owner.pk) or (address and address == issue.reporter_email):
            return None  # the reporter's own "fixed" notice already reaches this person
    if not owner and not address:
        return None
    from .notify import FAMILY
    feature, stream = FAMILY[issue.area]
    space, (subject, text) = issue.makerspace, copy(issue, loan, outcome)
    version = _revision(issue, outcome, owner.pk if owner else None)
    result = fanout(row=issue, space=space, feature=feature, stream=stream, event=EVENT, source_kind=SOURCE,
                    revision=version, owner=owner, staff=False, rooms=False,
                    owner_body=body(subject, text, local_link(space, "member")) if owner else None,
                    context={"issue_id": issue.pk, "area": issue.area, "outcome": outcome})
    if owner is None:  # account-less borrowers have no envelope; the one direct email stands
        direct_mail_unless_routed(space=space, source_kind=SOURCE, row=issue, revision=version, event=EVENT,
                                  owner=None, to_email=address, subject=subject, text=text, stream="maintenance",
                                  audience="requester", feature=feature, address_owner=False)
    return result


def eligible(envelope):
    from apps.accounts import rbac
    from apps.maintenance.models import IssueReport
    from . import areas
    issue = rbac.scope_notification_policy(IssueReport.objects.all(), makerspace_id=envelope.makerspace_id).filter(
        pk=envelope.source_id).select_related("makerspace").first()
    if not (issue and envelope.event == EVENT and envelope.audience == "requester"
            and areas.area_on(issue.makerspace, issue.area)):
        return False
    outcome = (envelope.context or {}).get("outcome")
    loan = _loan(issue)
    return bool(loan and loan.requester_id == envelope.recipient_id and outcome in OUTCOMES
                and issue.state in (("fixed", "closed") if outcome == "fixed" else ("rejected",))
                and _revision(issue, outcome, envelope.recipient_id) == envelope.revision)


def register():
    from apps.integrations.notification_sources import NotificationSource, register_source
    register_source(SOURCE, NotificationSource(eligible))
