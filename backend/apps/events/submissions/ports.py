"""Mandatory cross-lane boundaries. G installs concrete providers before mounting.

Authorization is checked again under the caller's ordered source/PII/event locks.
These server-side values never come from HTTP input. Missing adapters fail closed.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import ContextManager, Protocol

from .errors import SubmissionError


@dataclass(frozen=True)
class SubmissionContext:
    event: object
    team_id: int | None
    member_ids: tuple[int, ...]
    leader_id: int | None
    deadline: datetime
    grace_seconds: int = 0
    late_policy: str = "reject"
    managed: bool = False
    budget_bytes: int | None = None
    file_caps: dict[str, int] = field(default_factory=dict)
    group_caps: dict[str, int] = field(default_factory=dict)


class SubmissionBoundary(Protocol):
    def locked(self, *, actor, event_id: int, team_id: int | None, action: str) -> ContextManager[SubmissionContext]:
        """atomic: source/account/PII fences → authority → event → team locks.

        Recheck active actor, host/origin, events.hackathons + enabled config,
        servability and A eligible team/C-or-A participant. Moderation requires
        event_authority.require(actor,event,'manage_hackathon'). No S3/KMS I/O.
        """
        ...

    def lock_roster(self, *, context: SubmissionContext) -> None: ...
    def validate_project(self, *, context: SubmissionContext, project: dict, final: bool) -> dict:
        """Return F-canonical project answers (hidden answers omitted), after D
        same-event track/prize slots and A attendance/CoC/size checks.
        """
        ...

    def invalidate_snapshot(self, *, context: SubmissionContext, snapshot_id: int) -> None:
        """D invalidates current assignments/scores/public projections in this tx."""
        ...

    def invalidate_participant_asset_locked(self, *, context: SubmissionContext, member_id: int,
                                             asset_id: int, replacing: bool) -> None:
        """D revokes canonical consent/history for this deleted asset, or all
        older resumes when replacing=True. No second consent writer in B/C.
        """
        ...

    def receipt(self, *, event_id: int, actor_id: int, operation_id: str, digest: str) -> dict | None: ...
    def store_receipt(self, *, event_id: int, actor_id: int, operation_id: str, digest: str, result: dict) -> None: ...

    def storage_pool_locked(self, *, context: SubmissionContext, asset, operation: str, bytes: int) -> None:
        """G typed hackathon pool/tenant/provider accounting, idempotent by asset
        public_id+operation. Never reapply the ordinary tenant base entitlement.
        """
        ...


_boundary = None


def install_boundary(provider: SubmissionBoundary):
    global _boundary
    if _boundary is not None and _boundary is not provider:
        raise RuntimeError("Submission boundary already installed")
    _boundary = provider


def boundary():
    if _boundary is None:
        raise SubmissionError("programme_adapter_unavailable", 503)
    return _boundary
