"""J/I domain chunk contract. These types do not implement scheduling or locks."""

from dataclasses import dataclass, field
from typing import Literal, Protocol, TypedDict
from uuid import UUID

TICK_LOCK_NAMESPACE = 0x434C544B  # CLTK; two-int PostgreSQL advisory-lock namespace
CHECKPOINT_MAX_BYTES = 16384
TICK_REQUEST_MAX_BYTES = 1024

JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
ChunkOutcome = Literal["completed", "deferred", "failed", "unavailable"]


class ChunkContext(Protocol):
    """J supplies a guard-bound context; domain code checks it before effects.

    deadline is monotonic, not a wall-clock lease. check_active raises on guard
    loss/uncertainty and must never reconnect and bless a stale attempt.
    """

    attempt_id: UUID
    generation: int
    deadline: float

    def remaining_seconds(self) -> float: ...

    def check_active(self) -> None: ...


@dataclass(frozen=True, slots=True)
class ChunkResult:
    outcome: ChunkOutcome
    checkpoint: dict[str, JsonValue] = field(default_factory=dict)
    processed: int = 0
    reason_code: str = ""


class ChunkRunner(Protocol):
    def __call__(
        self, *, context: ChunkContext, checkpoint: dict[str, JsonValue], limit: int,
    ) -> ChunkResult: ...


@dataclass(frozen=True, slots=True)
class PeriodicJob:
    key: str
    task_path: str
    interval_seconds: int
    free_policy: Literal["bounded", "resumable", "unavailable"]
    chunk_path: str | None = None
    unavailable_reason: str = ""
    initial_due: bool = False
    priority: Literal["normal", "reminder", "outbox", "retained"] = "normal"


class TickResponse(TypedDict):
    run_id: str
    elapsed_seconds: float
    completed: int
    deferred: int
    failed: int
    reasons: list[str]
