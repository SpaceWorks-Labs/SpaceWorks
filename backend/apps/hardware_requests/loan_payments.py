"""Loan charges: the payments boundary for hardware loans.

Mirrors `apps/makerspaces/membership_payments.py`. Every entry point swallows payment
failures, because a provider outage must never stop a handover or a return. Amounts come
from the pricing kernel (`apps.payments.pricing`, lane L15). The workflow modules call in
at these points, and only they may:

* `require_deposit_settled` -- the reviewed-issue gate, run BEFORE the QR/evidence Hard
  Rules. It only ever refuses when `loan_deposit_blocks_issue` is on and the deposit is
  unpaid; it raises the deposit itself so the member has something to pay.
* `on_request_issued` -- after ANY issue commits (reviewed, direct, kiosk, self-checkout):
  the deposit (never blocking) and rental charged at checkout (A1, A10).
* `on_request_closed` -- after a return closes the loan: rental charged at return, the
  late fee (computed once, never mutated), and cancel a deposit that was never collected.
* `charge_accountability` -- staff set a damage / lost charge on one accountability row.

Amounts are `Decimal` major units, like every Payment row. Never floats.
"""

from apps.hardware_requests.loan_charges_common import (
    CLOSED_STATUSES,
    ZERO,
    loans_enabled,
)
from apps.hardware_requests.loan_charges_damage import (
    charge_accountability,
    return_evidence_id,
    suggestion,
)
from apps.hardware_requests.loan_charges_issue import (
    deposit_amount,
    on_request_issued,
    raise_deposit,
    require_deposit_settled,
)
from apps.hardware_requests.loan_charges_rental import raise_rental
from apps.hardware_requests.loan_charges_return import (
    on_request_closed,
    raise_late_fee,
)

__all__ = [
    "CLOSED_STATUSES",
    "ZERO",
    "charge_accountability",
    "deposit_amount",
    "loans_enabled",
    "on_request_closed",
    "on_request_issued",
    "raise_deposit",
    "raise_late_fee",
    "raise_rental",
    "require_deposit_settled",
    "return_evidence_id",
    "suggestion",
]
