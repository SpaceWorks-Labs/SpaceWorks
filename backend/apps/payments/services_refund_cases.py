"""Opening, upgrading and closing refund cases. No function here moves money.

Lock order everywhere: domain row (held by the caller) -> Payment -> RefundCase ->
Refund, matching `settle_refund` (Payment -> Refund). Every writer locks the Payment
first, so the one-active-case and one-due-case rules are decided under that lock and
a booking cancellation can never hit an IntegrityError on them (R1).
"""

from django.utils.translation import gettext
from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.payments.exceptions_refunds import RefundCaseConflict, RefundNotAllowed
from apps.payments.models import Payment, RefundCase
from apps.payments.refund_policy import area_for, assess, refundable_balance

SETTLED = (Payment.Status.PAID_ONLINE, Payment.Status.PAID_OFFLINE)


def _lock_payment(payment_id):
    return Payment.objects.select_for_update(of=("self",)).select_related("makerspace").get(pk=payment_id)


def _active(locked):
    return RefundCase.objects.select_for_update().filter(
        payment=locked, status__in=RefundCase.ACTIVE_STATUSES,
    ).first()


def record_case(actor, action, case, **meta):
    audit.record(actor, action, makerspace=case.payment.makerspace, target=case.payment,
                 meta={"case_id": case.pk, "payment_id": case.payment_id, "kind": case.kind,
                       "status": case.status, **meta})


def _notify(case, event):
    from apps.payments.notifications_refund_cases import notify_refund_case
    notify_refund_case(case, event)


@transaction.atomic
def open_due_case(payment, *, reason_code, actor, cancelled_at=None):
    """Record what a cancellation of a SETTLED charge entitles the member to (R5).

    Nothing opens when the policy owes nothing. An existing active case -- typically a
    member's own request -- is upgraded in place instead of a second one opening (R1).
    A payment is assessed under policy at most once: a due case is never repeated.
    """
    locked = _lock_payment(payment.pk)
    if locked.status not in SETTLED or locked.subject_type == Payment.SubjectType.LOAN_DEPOSIT:
        return None
    if RefundCase.objects.filter(payment=locked, kind=RefundCase.Kind.DUE).exists():
        return None
    due, snapshot = assess(locked, reason_code=reason_code, cancelled_at=cancelled_at)
    if due <= 0:
        return None
    case = _active(locked)
    if case is not None:
        case.kind, case.reason_code, case.due_amount, case.policy_snapshot = (
            RefundCase.Kind.DUE, reason_code, due, snapshot)
        case.save(update_fields=["kind", "reason_code", "due_amount", "policy_snapshot", "updated_at"])
        record_case(actor, "payment.refund_case_updated", case, due_amount=str(due), reason_code=reason_code)
    else:
        case = RefundCase.objects.create(
            payment=locked, kind=RefundCase.Kind.DUE, area=area_for(locked), reason_code=reason_code,
            due_amount=due, policy_snapshot=snapshot,
        )
        record_case(actor, "payment.refund_case_opened", case, due_amount=str(due), reason_code=reason_code)
    _notify(case, "refund_due_opened")
    return case


@transaction.atomic
def request_refund(payment, *, member, reason):
    """A member asks for money back on their own settled charge; staff decide."""
    locked = _lock_payment(payment.pk)
    if locked.member_id != member.pk:
        raise RefundNotAllowed(gettext("Only the payer can ask for a refund."), "refund_request_not_allowed")
    if locked.status not in SETTLED:
        raise RefundNotAllowed(gettext("Only a paid charge can be refunded."), "refund_not_settled")
    if locked.subject_type == Payment.SubjectType.LOAN_DEPOSIT:
        # A deposit has its own release path once the loan closes (R8).
        raise RefundNotAllowed(gettext("Deposits are released by staff when the loan closes."), "refund_request_not_allowed")
    if refundable_balance(locked) <= 0:
        raise RefundNotAllowed(gettext("This charge has already been refunded in full."), "refund_exceeds_balance")
    reason = (reason or "").strip()[:500]
    case = _active(locked)
    if case is not None:
        if case.kind == RefundCase.Kind.DUE and case.requested_by_id is None:
            # The space already owes something here; the member's words join that case.
            case.member_reason, case.requested_by = reason, member
            case.save(update_fields=["member_reason", "requested_by", "updated_at"])
            record_case(member, "payment.refund_case_updated", case, requested=True)
            _notify(case, "refund_request_received")
            return case
        raise RefundCaseConflict(gettext("A refund request is already open for this charge."), "refund_request_exists",
                                 case_id=case.pk)
    case = RefundCase.objects.create(
        payment=locked, kind=RefundCase.Kind.REQUEST, area=area_for(locked),
        reason_code=RefundCase.ReasonCode.MEMBER_REQUEST, member_reason=reason, requested_by=member,
    )
    record_case(member, "payment.refund_case_opened", case, reason_code=case.reason_code)
    _notify(case, "refund_request_received")
    return case


@transaction.atomic
def withdraw_request(case, *, member):
    """The member takes back their own request. A policy assessment is not theirs (R1)."""
    _lock_payment(case.payment_id)
    locked = RefundCase.objects.select_for_update().select_related("payment__makerspace").get(pk=case.pk)
    if locked.requested_by_id != member.pk:
        raise RefundCaseConflict(gettext("Only the member who asked can withdraw."), "refund_case_not_withdrawable")
    if locked.kind != RefundCase.Kind.REQUEST or locked.status != RefundCase.Status.OPEN:
        raise RefundCaseConflict(gettext("This refund can no longer be withdrawn."), "refund_case_not_withdrawable")
    locked.status, locked.decided_at = RefundCase.Status.WITHDRAWN, timezone.now()
    locked.save(update_fields=["status", "decided_at", "updated_at"])
    record_case(member, "payment.refund_case_withdrawn", locked)
    return locked


def approved_cases_for_refund(refund_id):
    """Lock the approved case(s) whose latest attempt is `refund_id`. Caller holds the Payment lock."""
    return list(RefundCase.objects.select_for_update().select_related("payment__makerspace").filter(
        refund_id=refund_id, status=RefundCase.Status.APPROVED))


def mark_approval_failed(cases, refund, *, actor):
    for case in cases:
        case.status = RefundCase.Status.APPROVAL_FAILED
        case.save(update_fields=["status", "updated_at"])
        record_case(actor, "payment.refund_case_approval_failed", case, refund_id=refund.pk)
        _notify(case, "refund_approval_failed")


def void_exhausted_cases(locked, *, actor, reason="balance_exhausted"):
    """Close active cases once nothing is left to refund on the charge (R7).

    Called by every path that adds a counted refund, inside its Payment lock -- a staff
    refund raised outside the case must not leave a case promising money that is gone.
    """
    if refundable_balance(locked) > 0:
        return []
    closed = []
    for case in RefundCase.objects.select_for_update().filter(payment=locked, status__in=RefundCase.ACTIVE_STATUSES):
        case.status, case.decided_at = RefundCase.Status.VOID, timezone.now()
        case.save(update_fields=["status", "decided_at", "updated_at"])
        record_case(actor, "payment.refund_case_voided", case, reason=reason)
        closed.append(case)
    return closed


@transaction.atomic
def void_reversed_due_case(payment, *, reason_code, actor, reason):
    """Close the OPEN due case a now-reversed cause opened (a reinstated project). Returns the case, or None.

    Only a case still awaiting staff is voided; one already approved (or failed after approval) is staff's
    to decline, so the caller refuses the reversal instead of overriding a decision.
    """
    locked = _lock_payment(payment.pk)
    case = RefundCase.objects.select_for_update().filter(
        payment=locked, kind=RefundCase.Kind.DUE, reason_code=reason_code, status=RefundCase.Status.OPEN).first()
    if case is None:
        return None
    case.status, case.decided_at = RefundCase.Status.VOID, timezone.now()
    case.save(update_fields=["status", "decided_at", "updated_at"])
    record_case(actor, "payment.refund_case_voided", case, reason=reason)
    return case
