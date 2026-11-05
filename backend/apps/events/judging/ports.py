"""Value-only integrations supplied by A/B/C/E/G; absent adapters fail closed.

No lane-owned fallback guesses another lane's schema, authority or storage policy.
Install once at app startup, after G's model/source/PII/authority registries.
"""

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Protocol

from apps.events.contracts.providers import LockedContext, ReadPurpose
from apps.events.contracts.subjects import AnswerSubject
from .errors import ProgrammeError


@dataclass(frozen=True, kw_only=True)
class PublicLink:
    id: int
    kind: str
    url: str


@dataclass(frozen=True, kw_only=True)
class Snapshot:
    id: int
    event_id: int
    team_id: int
    member_ids: tuple[int, ...]
    track_ids: tuple[int, ...]
    prize_ids: tuple[int, ...]
    title: str
    description: str
    content_sha256: str
    eligible: bool
    current: bool
    metadata_public: bool
    public_asset_ids: tuple[int, ...]
    public_links: tuple[PublicLink, ...]
    expires_at: datetime | None
    room: str = ""
    judge_asset_ids: tuple[int, ...] = ()
    judge_links: tuple[PublicLink, ...] = ()
    stage_id: int | None = None  # #178: the submission stage that froze it.


@dataclass(frozen=True, kw_only=True)
class Judge:
    role_assignment_id: int
    event_id: int
    member_id: int
    active: bool  # C/G must include current judge entitlement/grant, source reissue and time window.
    track_ids: tuple[int, ...] = ()
    room: str = ""


@dataclass(frozen=True, kw_only=True)
class Sponsor:
    id: int
    event_id: int
    name: str
    active: bool
    track_ids: tuple[int, ...]
    disclosure_revision: int = 1


@dataclass(frozen=True, kw_only=True)
class ParticipantAsset:
    id: int
    event_id: int
    member_id: int
    sha256: str
    state: str
    expires_at: datetime | None
    current: bool
    purpose: str = "resume"


class ProgrammePorts(Protocol):
    def require_programme(self, event, *, gallery: bool = False) -> None: ...

    def require_public_origin(self, event, request_context) -> None:
        """Exact host/origin/edition/target policy, including authenticated API clients."""
        ...

    def owner_subject(self, *, event_id: int, member_id: int) -> AnswerSubject:
        """A/C resolve a live participant OR role-only contributor; no membership prerequisite."""
        ...

    def fences(self, *, tenant_ids: tuple[int, ...], account_ids: tuple[int, ...]) -> AbstractContextManager: ...

    def lock_authority(self, *, actor_id: int, event):
        """Fresh actor + membership/grant/org authority locks, NEVER User/key row locks.

        G must not route this to the legacy resource_grant_locks helper, which
        locks User after Event. Account fences already precede the event lock.
        """
        ...

    def assert_lock_context(self, locks: LockedContext) -> None:
        """Attest G's already-acquired fences, event, authority and parent locks."""
        ...

    def snapshots(self, event_id: int, stage_id: int | None = None) -> tuple[Snapshot, ...]: ...

    def track_occupancy_locked(self, *, event_id: int, track_ids: tuple[int, ...],
                               exclude_team_id: int, locks: LockedContext) -> dict[int, int]:
        """B counts current submitted/locked/review/judged projects, including pending triage;
        withdrawn/disqualified/ineligible rows and this team's previous snapshot do not reserve.
        """
        ...

    def snapshot(self, snapshot_id: int) -> Snapshot: ...

    def judges(self, event_id: int) -> tuple[Judge, ...]: ...

    def judge(self, role_assignment_id: int) -> Judge: ...

    def is_conflicted(self, *, member_id: int, team_id: int, round_id: int) -> bool: ...

    def shortlist_signals(self, *, event_id: int) -> tuple[dict, ...]:
        """C's private production-only nomination/ratings/top-two summaries.
        Practice data, private notes and mentor identities are excluded.
        """
        ...

    def require_team_member(self, *, event_id: int, team_id: int, member_id: int,
                            sealed_member_ids: tuple[int, ...], leader: bool = False) -> None: ...

    def lock_team(self, *, event_id: int, team_id: int, locks: LockedContext) -> None:
        """A locks the exact event-owned team parent before D's consent children."""
        ...

    def require_subject_owner(self, *, actor_id: int, subject: AnswerSubject) -> None: ...

    def participant_asset(self, asset_id: int) -> ParticipantAsset: ...

    def sponsor(self, sponsor_id: int) -> Sponsor: ...

    def sponsors(self, event_id: int) -> tuple[Sponsor, ...]: ...

    def sponsor_rep_tracks(self, *, event_id: int, sponsor_id: int, actor_id: int) -> tuple[int, ...]: ...

    def public_member_card(self, *, event_id: int, member_id: int, scope: str) -> dict | None: ...

    def public_asset(self, *, event_id: int, asset_id: int) -> dict:
        """B allowlisted public ID/kind/MIME/bytes/state/hash, NEVER keys or filenames."""
        ...

    def stream_asset(self, *, asset_id: int, snapshot_id: int | None, actor_id: int | None,
                     purpose: ReadPurpose, request, reauthorize: Callable[[], None]):
        """B bounded stream; reauthorize before storage and EVERY chunk, no redirects."""
        ...

    def publish_retention_locked(self, *, event_id: int, first_published_at: datetime,
                                 locks: LockedContext) -> None:
        """A/B own first-results anchor; set once, never extend on correction."""
        ...

    def notify_intent(self, notice_id: int) -> None:
        """F/G enqueue source-backed notice; periodic sweeper recovers broker loss."""
        ...


_installed: ProgrammePorts | None = None


def install(ports: ProgrammePorts):
    global _installed
    _installed = ports


def runtime() -> ProgrammePorts:
    if _installed is None:
        raise ProgrammeError("programme_unavailable", "The event programme is temporarily unavailable.", status=503)
    return _installed
