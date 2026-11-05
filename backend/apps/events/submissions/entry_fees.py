"""L21b entry fee per project (X50). The project stays a draft until its fee is paid or waived.

The team leader raises the charge (``request_entry_fee``) and pays it online or at the desk; the
submit transition refuses with ``entry_fee_required`` until then. Disqualification voids a pending fee;
a PAID fee opens a refund DUE case only when the event's "refund on disqualification" switch is set
(#59). Nothing is ever refunded automatically. With ``events.entry_fees`` off nothing is charged.
"""

from django.db import transaction
from django.http import Http404

from .errors import SubmissionError


def entry_fee(event):
    from apps.events.judging.feature import ENTRY_FEES, enabled
    from apps.events.judging.options import option
    from apps.payments.availability import charge_tracking_enabled
    if not enabled(event.makerspace, ENTRY_FEES) or not charge_tracking_enabled(event.makerspace, "events"):
        return None  # Nothing is charged, so nothing is held.
    return option(event, "entry_fee")


def require_submit_paid(project, event, team):
    """Called by the submit transition: the entry fee and a paid team's charge must be settled."""
    from apps.events.hackathons.team_payments import team_payment_settled
    from apps.events.programme_charges import PAID_OR_WAIVED, find_charge
    if entry_fee(event):
        payment = find_charge(event, "submission_fee", project.pk) if project.pk else None
        if payment is None or payment.status not in PAID_OR_WAIVED:
            raise SubmissionError("entry_fee_required", 402)
    if not team_payment_settled(team):
        raise SubmissionError("team_payment_required", 402)


def projection(event, project):
    from apps.events.programme_charges import find_charge
    payment = find_charge(event, "submission_fee", project.pk) if project else None
    amount = entry_fee(event)
    return {"required": bool(amount), "amount": amount, "payment_id": payment.pk if payment else None,
            "status": payment.status if payment else ("not_raised" if amount else "not_required"),
            "currency": payment.currency if payment else ""}


@transaction.atomic
def request_entry_fee(*, actor, event, team):
    """The leader raises the project's entry fee charge (idempotent). Returns the projection."""
    from apps.events.models import HackathonSubmission
    from apps.events.programme_charges import raise_charge
    if team.leader_id != actor.pk:
        raise SubmissionError("leader_required", 403)
    amount = entry_fee(event)
    if not amount:
        raise Http404
    project = HackathonSubmission.objects.filter(event_id=event.pk, team_id=team.pk).first()
    if project is None:
        raise SubmissionError("project_draft_required", 409)  # Save the draft first; it stays a draft.
    raise_charge(event=event, subject_type="submission_fee", subject_id=project.pk, member=actor, amount=amount,
                 actor=actor, audit_action="event.submission.fee_raised",
                 target={"type": "project", "id": project.pk, "label": "Project entry fee"})
    return projection(event, project)


def on_disqualified(*, event, project, actor):
    """Inside the disqualifying transaction: void a pending fee; a paid one may open a DUE case."""
    from apps.events.judging.options import option
    from apps.events.programme_charges import close_charge
    close_charge(event=event, subject_type="submission_fee", subject_id=project.pk, actor=actor,
                 reason_code="submission_disqualified", audit_action="event.submission.fee_closed",
                 open_due=bool(option(event, "refund_on_disqualification")))
    # Hack-money G16: a prize already paid to this project is owed back. Opening a recovery never
    # charges anyone; staff record repayment (a ledger receipt) or waive it.
    from apps.events.judging.prize_outcomes import open_recoveries_locked
    open_recoveries_locked(event=event, project=project, actor=actor)


def on_withdrawn(*, event, project, actor):
    """Hack-money G2, inside the withdrawing transaction: void a pending fee; a paid one opens a DUE
    case only with the event's "refund on withdrawal" switch on."""
    from apps.events.judging.options import option
    from apps.events.programme_charges import close_charge
    close_charge(event=event, subject_type="submission_fee", subject_id=project.pk, actor=actor,
                 reason_code="submission_withdrawn", audit_action="event.submission.fee_closed",
                 open_due=bool(option(event, "refund_on_withdrawal")))


def on_shortlist_published(*, event, actor):
    """Hack-money G2: with "refund if not shortlisted" on, a published shortlist opens a DUE case on
    every PAID entry fee of a submitted project that did not advance. Off: paid fees stand.

    Who advanced is asked through `judging.shortlist_seam`, the one place the stage engine replaces.
    """
    from apps.events.judging.options import option
    from apps.events.judging.shortlist_seam import not_shortlisted_project_ids
    from apps.events.programme_charges import close_charge
    if not entry_fee(event) or not option(event, "refund_if_not_shortlisted"):
        return
    for project_id in not_shortlisted_project_ids(event):
        close_charge(event=event, subject_type="submission_fee", subject_id=project_id, actor=actor,
                     reason_code="not_shortlisted", audit_action="event.submission.fee_closed")
