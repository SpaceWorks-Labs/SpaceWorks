"""Core-owned terminal anchors; no lookup into Events or reimbursements."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .validation import PayoutValidationError, aware


RECEIPT_DAYS = 2555
PAYEE_DAYS = 30
ABANDONED_HOURS = 24


@dataclass(frozen=True, kw_only=True)
class Closure:
    terminal_financial_at: datetime
    reason_code: str
    operation_id: object
    policy_revision: int
    retention_days: int

    def __post_init__(self):
        from uuid import UUID
        from .validation import reason_code
        aware(self.terminal_financial_at)
        reason_code(self.reason_code)
        if not isinstance(self.operation_id, UUID):
            raise PayoutValidationError("invalid_operation_id")
        if type(self.policy_revision) is not int or self.policy_revision < 1:
            raise PayoutValidationError("invalid_retention_policy")
        if type(self.retention_days) is not int or not 1 <= self.retention_days <= 36500:
            raise PayoutValidationError("invalid_retention_policy")

    @property
    def expires_at(self):
        return self.terminal_financial_at + timedelta(days=self.retention_days)


def deletion_due(*, now, closure, liability_open, hold_active):
    aware(now)
    if type(liability_open) is not bool or type(hold_active) is not bool:
        raise PayoutValidationError("invalid_retention_state")
    return bool(closure is not None and not liability_open and not hold_active and now >= closure.expires_at)


def retain_closure(previous, proposed):
    """Purge/retry cannot reset the clock or shorten preserved financial evidence."""
    if previous is None:
        return proposed
    if previous != proposed:
        raise PayoutValidationError("financial_closure_conflict")
    return previous


def payee_purge_days():
    """Deployment window between a payee's terminal anchor and its purge."""
    from django.conf import settings
    return getattr(settings, "EVENT_REIMBURSEMENT_PAYEE_PURGE_DAYS", PAYEE_DAYS)
