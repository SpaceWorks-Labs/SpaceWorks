"""Safe projections for S/E/J -> I -> F. No credentials or tenant totals leak."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, TypedDict
from uuid import UUID

UsageState = Literal["ok", "warning", "critical", "reached", "unknown", "stale"]


class UsageMetric(TypedDict):
    used: int | None
    cap: int | None
    unit: Literal["bytes", "recipients"]
    state: UsageState
    sampled_at: str | None
    source: str
    cap_source: str
    cap_verified_on: str | None
    scope: Literal["deployment", "tenant", "provider_account"]
    uncertain: int
    reason_code: str


class TickFreshness(TypedDict):
    last_contact_at: str | None
    last_completed_at: str | None
    age_seconds: int | None
    interval_seconds: int
    state: Literal["ok", "late", "never", "failed", "unknown"]
    failed_tasks: int


class QuotaSnapshot(TypedDict):
    profile: Literal["free"]
    visibility: Literal["deployment", "tenant"]
    database: UsageMetric | None
    objects: UsageMetric
    email: UsageMetric
    email_pending: int | None
    email_uncertain: int | None
    tick: TickFreshness
    notices: list[str]


@dataclass(frozen=True, slots=True)
class EmailBudgetConfig:
    account_key: str  # opaque operator alias, never an API key or mailbox
    daily_cap: int
    monthly_cap: int | None
    reset_timezone: str
    cap_source: str
    cap_verified_on: str


@dataclass(frozen=True, slots=True)
class MailReservation:
    reservation_id: UUID | None
    outcome: Literal["reserved", "deferred", "disabled"]
    retry_at: datetime | None = None
    reason_code: str = ""


class MailBudget(Protocol):
    """E implements atomic account-wide reserve; I supplies durable models.

    Acceptance uncertainty stays charged. Only definite nonacceptance releases
    units. An idempotency key identifies one delivery, including all retries.
    """

    def reserve(
        self, *, config: EmailBudgetConfig, delivery_key: str, recipients: int,
        now: datetime,
    ) -> MailReservation: ...

    def settle(
        self, *, reservation_id: UUID,
        outcome: Literal["accepted", "not_accepted", "uncertain"],
    ) -> None: ...
