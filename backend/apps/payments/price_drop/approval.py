"""Who decides a price-difference refund case (#163A; #171 (3)).

A difference case -- a price lowered after payment, or a prepaid job that cost less
than its quote -- is approved or declined by the Space Manager or a FINANCE ADMIN (a
person holding both view_finance and record_payment in that space). The area managers
who decide ordinary cancellation cases (a Booking Manager, a Machine Manager) cannot:
the money was right when it was taken, and giving part of it back is a finance call.

A case is a difference case when it opened for one of those reasons, or when an L24
share was added to an already open case (one active case per charge, R1).

A member cancelling a prepaid job before it starts (#171 (2), `job_cancelled`) is an
ordinary cancellation: the job's Machine Manager decides it like a staff cancellation.
"""

from django.utils.translation import gettext
from rest_framework.exceptions import PermissionDenied

from apps.accounts import rbac
from apps.payments.models import RefundCase
from apps.payments.price_drop import SOURCES

DIFFERENCE_REASONS = (RefundCase.ReasonCode.PRICE_DROP, RefundCase.ReasonCode.QUOTE_DIFFERENCE)


def is_difference_case(case):
    """Opened for a price difference: approving it never ends a membership term."""
    return case.reason_code in DIFFERENCE_REASONS


def needs_finance_approval(case):
    if is_difference_case(case):
        return True
    return any(share.get("source") in SOURCES for share in (case.policy_snapshot or {}).get("shares", []))


def is_finance_approver(actor, makerspace_id):
    if rbac.is_space_manager_identity(actor, makerspace_id):
        return True
    return (rbac.can(actor, rbac.Action.VIEW_FINANCE, makerspace_id)
            and rbac.can(actor, rbac.Action.RECORD_PAYMENT, makerspace_id))


def require_decider(actor, payment, case):
    """Raise unless `actor` may approve or decline `case` on `payment`."""
    if needs_finance_approval(case):
        if not is_finance_approver(actor, payment.makerspace_id):
            raise PermissionDenied(gettext("A price-difference refund is approved by the Space Manager or a finance admin."))
        return
    from apps.payments.reconciliation_authority import _require_subject_authority
    _require_subject_authority(actor, [payment])
