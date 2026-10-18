"""Required cross-lane integrations. G installs one complete adapter at startup.

No permission or crypto fallback: an uninstalled adapter refuses before mutation.
The protocols deliberately exchange IDs and value objects rather than writable ORM rows.
"""
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Protocol

from apps.events.contracts.providers import LockedContext
from apps.events.contracts.subjects import AnswerSubject
from .errors import ProgrammeError


class RoleForms(Protocol):
    def validate_schema(self, *, schema: dict) -> dict: ...
    def context(self, *, actor_id: int, event_id: int, schema: dict) -> dict: ...
    def lock_locked(self, *, subject: AnswerSubject, locks: LockedContext) -> None: ...
    def prepare(self, *, actor_id: int, subject: AnswerSubject, schema: dict,
                payload: dict, submit: bool, previous_answers: str) -> object:
        """F validation + P key/derivation preparation, outside event transactions."""
        ...

    def apply_locked(self, *, prepared: object, subject: AnswerSubject,
                     locks: LockedContext) -> dict:
        """Return answers_json/consent_revision/schema_version/save_intent. No KMS."""
        ...

    def require_approval_locked(self, *, subject: AnswerSubject, locks: LockedContext) -> None: ...
    def project(self, *, subject: AnswerSubject, audience: str) -> dict: ...
    def review_date_locked(self, *, subject: AnswerSubject, revision: int,
                           as_of_date: str, locks: LockedContext) -> None: ...
    def validate_round(self, *, schema: dict, answers: dict) -> dict: ...
    def reopen_locked(self, *, subject: AnswerSubject, previous_version: int,
                      locks: LockedContext) -> None:
        """P archives frozen DOB/date sources and starts a fresh unconfirmed revision.

        No DOB, computed age, key provisioning or external I/O crosses this port.
        """
        ...
    def export_owner(self, *, subject: AnswerSubject, actor_id: int) -> dict: ...


class GrantSources(Protocol):
    def ensure_container_locked(self, *, event_id: int, member_id: int, actor_id: int,
                                locks: LockedContext) -> int:
        """Existing shared lifecycle's internal already-locked create/reuse method."""
        ...

    def write_display_union_locked(self, *, grant_id: int, permissions: tuple[str, ...],
                                   actor_id: int, locks: LockedContext) -> None:
        """Existing lifecycle, no manual-source hook recursion or authority widening."""
        ...


class TeamAccess(Protocol):
    def own_ids(self, *, actor_id: int, event_id: int) -> tuple[int, ...]: ...
    def member_ids(self, *, event_id: int, team_id: int) -> tuple[int, ...]: ...
    def require_member(self, *, actor_id: int, event_id: int, team_id: int) -> None: ...
    def require_eligible(self, *, event_id: int, team_id: int, at: datetime) -> None: ...
    def skills(self, *, event_id: int, team_id: int) -> tuple[str, ...]: ...
    def alias(self, *, event_id: int, team_id: int) -> str: ...
    def ids(self, *, event_id: int, practice_run_id: str | None) -> tuple[int, ...]: ...
    def require_practice(self, *, event_id: int, team_id: int, practice_run_id: str | None) -> None: ...
    def validate_import(self, *, event_id: int, rows: list[dict]) -> list[dict]: ...
    def import_locked(self, *, event_id: int, mapping: list[dict], practice_run_id: str | None,
                      locks: LockedContext) -> None: ...


class ProgrammePorts(Protocol):
    forms: RoleForms
    grants: GrantSources
    teams: TeamAccess

    def fences(self, *, tenant_ids: tuple[int, ...], account_ids: tuple[int, ...]
               ) -> AbstractContextManager[None]: ...
    def prepare_private_write(self, *, makerspace_id: int) -> None: ...
    def lock_authority_locked(self, *, actor_id: int, event_id: int, locks: LockedContext) -> None:
        """Membership/grant/organization locks only. Never lock User/AccountPiiKey."""
        ...
    def require_event_feature(self, *, event_id: int, feature: str) -> None: ...
    def require_role_audience(self, *, actor_id: int, event_id: int, posting_id: int) -> None: ...
    def visible_posting_ids(self, *, actor_id: int, event_id: int) -> tuple[int, ...]: ...
    def require_requirements(self, *, actor_id: int, assignment_id: int, shift_id: int | None,
                             override_ids: tuple[int, ...] = ()) -> None:
        """Validate live requirements; overrides cover only their exact training/briefing IDs.

        Always require real waiver and CoC evidence regardless of override records.
        """
        ...
    def delegation_scope(self, *, actor_id: int, target_id: int, permissions: tuple[str, ...],
                         operation: str, row_id: int | None) -> bool: ...
    def deliver_help(self, *, intent_id: int, recipient_ids: tuple[int, ...], payload: dict,
                      idempotency_key: str) -> None: ...
    def organizer_ids(self, *, event_id: int) -> tuple[int, ...]: ...
    def deliver_contribution(self, *, notice_id: int, idempotency_key: str) -> None: ...
    def enqueue_notice(self, *, kind: str, notice_id: int) -> None: ...


_adapter: ProgrammePorts | None = None


def install(adapter: ProgrammePorts):
    global _adapter
    _adapter = adapter


def ports() -> ProgrammePorts:
    if _adapter is None:
        raise ProgrammeError("programme_not_ready", "The programme is not ready.", status=503)
    return _adapter


def required_hook(adapter, name):
    hook = getattr(adapter, name, None)
    if not callable(hook):
        raise ProgrammeError("programme_not_ready", "The programme adapter is not ready.", status=503)
    return hook
