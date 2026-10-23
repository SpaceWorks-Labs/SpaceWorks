"""Loan deposits and late fees: the payments boundary for hardware loans.

Mirrors `apps/makerspaces/membership_payments.py`. Every entry point swallows payment
failures, because a provider outage must never stop a handover or a return. The
workflow module calls in at three points, and only the workflow module may:

* `require_deposit_settled` -- the issue gate, run BEFORE the QR/evidence Hard Rules.
  It only ever refuses when `loan_deposit_blocks_issue` is on and the deposit is unpaid;
  it raises the deposit itself so the member has something to pay.
* `raise_deposit` -- after the issue transition commits (non-blocking mode).
* `on_request_closed` -- after a return closes the loan: raise the late fee (computed
  once, never mutated) and cancel a deposit that was never collected.

Amounts are `Decimal` major units, like every Payment row. Never floats.
"""

from apps.hardware_requests.loan_charges_common import (
    CLOSED_STATUSES,
    ZERO,
    loans_enabled,
)
from apps.hardware_requests.loan_charges_issue import (
    deposit_amount,
    raise_deposit,
    require_deposit_settled,
)
from apps.hardware_requests.loan_charges_return import (
    on_request_closed,
    raise_late_fee,
)

__all__ = [
    "CLOSED_STATUSES",
    "ZERO",
    "deposit_amount",
    "loans_enabled",
    "on_request_closed",
    "raise_deposit",
    "raise_late_fee",
    "require_deposit_settled",
]
