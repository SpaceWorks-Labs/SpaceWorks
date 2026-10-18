"""G installs typed event-domain verification without core Accounts importing Events."""
from typing import Protocol
from dataclasses import dataclass

from .errors import SavedDetailsError, unavailable


@dataclass(frozen=True, kw_only=True)
class VerifiedIntentBinding:
    form_sha256: str
    canonical_answer_sha256: str
    event_date_revision: int
    chosen_fields: tuple[str, ...]


class IntentSubjectBinding(Protocol):
    def require_binding(self, *, prepared_subject: object, actual_subject: object, operation_id: object, locks: object) -> VerifiedIntentBinding:
        """Recheck real typed subject owner/event and new-subject operation receipt.

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
    if _provider is None:
        raise unavailable()
    result = _provider.require_binding(prepared_subject=prepared.subject, actual_subject=subject,
                                      operation_id=prepared.operation_id, locks=locks)
    if not isinstance(result, VerifiedIntentBinding):
        raise SavedDetailsError("invalid_subject", "Registration context not found.", 404)
    return result
