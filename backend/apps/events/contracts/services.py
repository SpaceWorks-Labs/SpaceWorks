"""Frozen service seams. No writable cross-package ORM objects cross these APIs."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from .providers import LockedContext
from .subjects import AnswerSubject


@dataclass(frozen=True, kw_only=True)
class DelegationScope:
    event_id: int
    track_ids: tuple[int, ...] = ()
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    helper_role: Literal["volunteer", "mentor", "judge", "sponsor_rep"]


class HelperDelegationPolicy(Protocol):
    def can_delegate_helpers(
        self, *, actor_id: int, target_id: int, permissions: tuple[str, ...],
        scope: DelegationScope,
    ) -> bool:
        """Live subset/time/track check at issue, redemption, edit and revoke.

        Does not change can_manage_grants or can(actor, event, None). manage_team
        cannot itself be delegated. Server reauthentication is checked separately.
        """
        ...


class AdmissionProvider(Protocol):
    def require_team_eligible(self, *, team_id: int, event_id: int, at: datetime) -> None: ...

    def transition_registration_locked(
        self, *, application_id: int, registration_id: int | None,
        transition: str, locks: LockedContext,
    ) -> int: ...


class TeamProvider(Protocol):
    def lock_roster_locked(self, *, team_id: int, locks: LockedContext) -> str: ...


class SnapshotAssets(Protocol):
    def require_ready_for_snapshot(
        self, *, asset_ids: tuple[int, ...], owner_team_id: int, event_id: int,
    ) -> tuple[int, ...]: ...


class SponsorConsentProvider(Protocol):
    """D is the sole model/workflow writer, including C role-only applicants."""

    def grant(
        self, *, subject: AnswerSubject, sponsor_id: int, asset_id: int,
        purpose: Literal["recruiting"], disclosure_revision: int, locks: LockedContext,
    ) -> int: ...

    def revoke(self, *, consent_id: int, actor_id: int, locks: LockedContext) -> None: ...

    def project_owner(self, *, event_id: int, member_id: int) -> dict: ...

    def require_effective_for_asset(
        self, *, event_id: int, member_id: int, sponsor_id: int, asset_id: int,
        purpose: Literal["recruiting"],
    ) -> None: ...


class ContributionProvider(Protocol):
    def sync_entitlement_locked(self, *, assignment_id: int, locks: LockedContext) -> None: ...


class ConflictProvider(Protocol):
    def is_conflicted(self, *, member_id: int, team_id: int, round_id: int) -> bool: ...


class CertificateProvider(Protocol):
    def issue(
        self, *, subject: AnswerSubject, kind: str, result_revision: int | None,
        actor_id: int,
    ) -> int: ...


class SectionProvider(Protocol):
    def project_public(self, *, event_id: int, section_id: int, request_context: object) -> dict: ...
