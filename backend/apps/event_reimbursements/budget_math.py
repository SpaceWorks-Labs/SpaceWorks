"""Integer budget invariant used exclusively by budget_service."""

from dataclasses import dataclass
from apps.payments.event_payouts.validation import PayoutValidationError, minor


@dataclass(frozen=True, kw_only=True)
class Balance:
    total_minor: int
    reserved_minor: int = 0
    committed_minor: int = 0

    def __post_init__(self):
        for value in (self.total_minor, self.reserved_minor, self.committed_minor):
            minor(value, zero=True)
        if self.available_minor < 0:
            raise PayoutValidationError("budget_exhausted")

    @property
    def available_minor(self):
        return self.total_minor - self.reserved_minor - self.committed_minor

    def change(self, *, total=0, reserved=0, committed=0):
        for value in (total, reserved, committed):
            minor(value, signed=True)
        return Balance(total_minor=self.total_minor + total,
                       reserved_minor=self.reserved_minor + reserved,
                       committed_minor=self.committed_minor + committed)


def settle_reservation(balance, *, held_minor, approved_minor):
    minor(held_minor, zero=True)
    minor(approved_minor, zero=True)
    if approved_minor > held_minor or held_minor > balance.reserved_minor:
        raise PayoutValidationError("invalid_budget_commitment")
    return balance.change(reserved=-held_minor, committed=approved_minor)


def cancel_commitment(balance, *, committed_minor, held_minor=0):
    minor(committed_minor, zero=True)
    minor(held_minor, zero=True)
    if committed_minor > balance.committed_minor or held_minor > balance.reserved_minor:
        raise PayoutValidationError("invalid_budget_commitment")
    return balance.change(reserved=-held_minor, committed=-committed_minor)
