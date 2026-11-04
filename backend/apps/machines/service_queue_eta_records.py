"""Records, vocabulary and boundary rounding for the pure queue-ETA simulator."""

import math
from dataclasses import dataclass, field
from datetime import timedelta

STEP_MINUTES = 5
OVERDUE_FLOOR_MINUTES = 5
CAPACITY_STATUSES = frozenset({"idle", "running"})

ESTIMATED, ROUGH, UNAVAILABLE = "estimated", "rough", "unavailable"
AWAITING = "awaiting_approval"
MISSING = "missing_estimate"
NO_MACHINE = "no_active_machine"
OVERDUE = "overdue_running_job"
UNKNOWN_RUN = "unknown_running_job"
INACTIVE = "inactive_scope"
COMPETING = "competing_scopes"
REASONS = (AWAITING, MISSING, NO_MACHINE, OVERDUE, UNKNOWN_RUN, INACTIVE, COMPETING)
BLOCKING = frozenset({MISSING, NO_MACHINE, UNKNOWN_RUN, INACTIVE})
SOFT = frozenset({AWAITING, OVERDUE, COMPETING})
CARRIED = frozenset({OVERDUE, COMPETING, MISSING, UNKNOWN_RUN})


@dataclass(frozen=True)
class MachineRecord:
    id: int
    group: tuple
    is_active: bool
    status: str

    @property
    def has_capacity(self):
        return self.is_active and self.status in CAPACITY_STATUSES


@dataclass(frozen=True)
class ScopeRecord:
    key: tuple
    group: tuple
    is_active: bool
    capacity: int | None = None
    machine_id: int | None = None


@dataclass(frozen=True)
class JobRecord:
    id: int
    scope: tuple
    status: str
    created_at: object
    minutes: int | None
    started_at: object = None
    machine_id: int | None = None
    # A batch run (#142 OQ-9): jobs sharing one machine run end together.
    batch_id: int | None = None


@dataclass
class Forecast:
    start: float | None = None
    finish: float | None = None
    actual_start: object = None
    reasons: set = field(default_factory=set)


def round_up(offset):
    """Round a future offset up to the next 5-minute boundary; never negative."""
    value = max(0.0, round(offset, 6))
    return int(math.ceil(value / STEP_MINUTES) * STEP_MINUTES)


def confidence(reasons):
    if reasons & BLOCKING:
        return UNAVAILABLE
    return ROUGH if reasons & SOFT else ESTIMATED


def ordered_reasons(reasons):
    return [reason for reason in REASONS if reason in reasons]


def project(now, forecast):
    """Boundary projection: one set of rounded offsets drives timestamps and minutes."""
    reasons = set(forecast.reasons)
    level = confidence(reasons)
    payload = {"calculated_at": now, "estimated_start_at": None, "estimated_finish_at": None,
               "start_in_minutes": None, "finish_in_minutes": None,
               "confidence": level, "reasons": ordered_reasons(reasons)}
    if level == UNAVAILABLE or forecast.start is None or forecast.finish is None:
        return payload
    finish = round_up(forecast.finish)
    if forecast.actual_start is not None:
        start_at, start = forecast.actual_start, 0
    else:
        start = round_up(forecast.start)
        start_at = now + timedelta(minutes=start)
    payload.update(estimated_start_at=start_at, estimated_finish_at=now + timedelta(minutes=finish),
                   start_in_minutes=start, finish_in_minutes=finish)
    return payload
