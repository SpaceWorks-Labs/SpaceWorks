"""G installs typed event-domain verification without core Accounts importing Events."""
from typing import Protocol
from dataclasses import dataclass
from uuid import UUID

from .errors import SavedDetailsError, unavailable


def require_subject(subject):
    """The domain supplies a model-free typed value, never a browser dict."""
    if (str(getattr(subject, "kind", "")) not in {"registration", "application", "role_assignment", "stage_response"}
            or any(type(getattr(subject, key, None)) is not int or getattr(subject, key) <= 0
                   for key in ("event_id", "owner_member_id"))):
        raise SavedDetailsError("invalid_subject", "Form context not found.", 404)
    existing, creation = getattr(subject, "subject_id", None), getattr(subject, "creation_operation_id", None)
    if ((existing is None) == (creation is None)
            or existing is not None and (type(existing) is not int or existing <= 0)
            or creation is not None and not isinstance(creation, UUID)):
        raise SavedDetailsError("invalid_subject", "Form context not found.", 404)


@dataclass(frozen=True, kw_only=True)
class VerifiedFormOperation:
    """G verifies UUIDv5 + its locked pending slot map before returning this.

    Stage ownership is resolved by R using owner_member_id; this is never passed
    through the closed registration/application DOB derivation resolver.
    """
    outer_operation_id: UUID
    slot: str
    operation_id: UUID
    event_id: int
    owner_member_id: int
    subject_kind: str
    subject_id: int


@dataclass(frozen=True, kw_only=True)
class VerifiedIntentBinding:
    form_sha256: str
    canonical_answer_sha256: str
    event_date_revision: int
    chosen_fields: tuple[str, ...]
    form_operation: VerifiedFormOperation | None = None


class IntentSubjectBinding(Protocol):
    def require_binding(self, *, prepared_subject: object, actual_subject: object, operation_id: object, locks: object) -> VerifiedIntentBinding:
        """Recheck real typed subject owner/event and new-subject operation receipt.

        For inline forms, recheck G's server-owned pending slot map and canonical
        child_form_operation_id against the bound rows, not an outer receipt that
        does not exist yet. Return VerifiedFormOperation with the live hashes.
        No account locks, key I/O or authority inferred from this argument object.
        The domain's own locked row/receipt is the authority. Return live hashes,
        date revision and explicitly selected visible field names after validation.
        """
        ...


_provider = None


def install_subject_binding(provider: IntentSubjectBinding):
    global _provider
    if _provider is not None and _provider is not provider:
        raise RuntimeError("Saved details subject binding already installed.")
    _provider = provider


def require_binding(prepared, subject, locks):
    require_subject(prepared.subject)
    require_subject(subject)
    if _provider is None:
        raise unavailable()
    result = _provider.require_binding(prepared_subject=prepared.subject, actual_subject=subject,
                                      operation_id=prepared.operation_id, locks=locks)
    if not isinstance(result, VerifiedIntentBinding):
        raise SavedDetailsError("invalid_subject", "Registration context not found.", 404)
    if prepared.outer_operation_id is not None:
        proof = result.form_operation
        expected = (prepared.outer_operation_id, prepared.form_slot, prepared.operation_id,
                    subject.event_id, subject.owner_member_id, str(subject.kind), subject.subject_id)
        if (not isinstance(proof, VerifiedFormOperation)
                or (proof.outer_operation_id, proof.slot, proof.operation_id, proof.event_id,
                    proof.owner_member_id, proof.subject_kind, proof.subject_id) != expected):
            raise SavedDetailsError("invalid_subject", "This preparation belongs to another form.", 409)
    return result
