"""ID-only cross-lane subject bindings; providers must recheck live ownership."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class SubjectKind(StrEnum):
    REGISTRATION = "registration"
    APPLICATION = "application"
    ROLE_ASSIGNMENT = "role_assignment"


@dataclass(frozen=True, kw_only=True)
class AnswerSubject:
    event_id: int
    owner_member_id: int
    kind: SubjectKind
    subject_id: int | None = None
    creation_operation_id: UUID | None = None

    def __post_init__(self):
        if not isinstance(self.kind, SubjectKind):
            raise ValueError("Use a typed answer subject kind.")
        ids = (self.event_id, self.owner_member_id)
        if any(type(value) is not int or value <= 0 for value in ids):
            raise ValueError("Subject bindings require positive integer IDs.")
        if (self.subject_id is None) == (self.creation_operation_id is None):
            raise ValueError("Bind one existing subject or one creation operation.")
        if self.subject_id is not None and (
            type(self.subject_id) is not int or self.subject_id <= 0
        ):
            raise ValueError("Use a positive subject ID.")
        if self.creation_operation_id is not None and not isinstance(
            self.creation_operation_id, UUID
        ):
            raise ValueError("Use a UUID creation operation.")


class SubjectResolver(Protocol):
    def require_owner(self, actor_id: int, subject: AnswerSubject) -> AnswerSubject:
        """Resolve typed FK, same event/member, standing and current authority."""
        ...
