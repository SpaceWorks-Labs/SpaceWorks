"""Required integration ports: G/F/P install these before routes are enabled.

None of these callbacks is an authorization fallback. Missing integration returns
503; the service cannot create an ordinary registration to bypass admission.
"""
from dataclasses import dataclass, field
from typing import Callable, Protocol
from contextlib import AbstractContextManager
from .admission_errors import fail


@dataclass(frozen=True)
class PreparedAnswers:
    snapshot: dict = field(repr=False)
    form_sha256: str
    normalized_input: dict = field(repr=False)
    subject: object
    trusted_registration_form: object = field(repr=False)
    saved_intent: object = field(default=None, repr=False)
    derivations: object = field(default=None, repr=False)


@dataclass(frozen=True)
class OwnerAnswers:
    answers: list
    answer_review: dict
    omitted_question_ids: tuple[str, ...] = ()


class RegistrationBridge(Protocol):
    def create_pending_locked(self, *, event, member, selection, contacts,
                              prepared, subject, locks):
        """Validate/redeem ticket/codes/waiver; pending only, no charge/QR.

        Called after the application PK exists. Mirror the SAME canonical
        application snapshot; never validate against Event.custom_form.
        """
        ...

    def transition_locked(self, *, application_id, registration_id, transition,
                          actor, reason_code, locks):
        """Existing services_registration_state writes status/calendar/ledger."""
        ...

    def mirror_answers_locked(self, *, application_id, registration_id, prepared, locks): ...


class FormPort(Protocol):
    def prepare(self, *, event, config, actor, subject, payload, draft) -> PreparedAnswers:
        """F validation + P key/derivation preparation, outside event locks."""
        ...

    def require_current_locked(self, *, event, config, prepared, locks): ...
    def attach_locked(self, *, application, prepared, locks, store_intent: bool): ...
    def validate_schema(self, schema): ...
    def project_owner(self, *, application, snapshot) -> OwnerAnswers: ...
    def lock_answers_locked(self, *, application, at, locks, closing=False): ...
    def archive_answers_locked(self, *, application, revision_id, locks): ...
    def project_intent(self, *, application): ...
    def date_review_locked(self, *, application, revision, as_of_date, locks): ...


@dataclass(frozen=True)
class AdmissionIntegrations:
    registration: RegistrationBridge
    forms: FormPort
    fences: Callable[..., AbstractContextManager]
    lock_event: Callable
    context_gate: Callable
    readiness: Callable
    public_profile: Callable
    reviewer_candidates: Callable
    subject_conflict: Callable
    has_submission: Callable
    reopen_submission_locked: Callable
    enqueue_notice: Callable
    assert_encryption_ready: Callable
    storage_budget_used: Callable
    storage_budget_limit: Callable
    upload_policy_supported: Callable
    default_attendance_required: Callable
    event_scopes: Callable
    lock_actor: Callable | None = None


_ports = None


def install(integrations: AdmissionIntegrations):
    global _ports
    if not isinstance(integrations, AdmissionIntegrations):
        raise TypeError("Install typed admission integrations.")
    _ports = integrations


def ports() -> AdmissionIntegrations:
    if _ports is None:
        fail("programme_dependency_unavailable", "Event admission is temporarily unavailable.", status=503)
    return _ports


def install_production(**providers):
    """Startup supplies F/P/C/B/E providers; registration and lock order are fixed."""
    from apps.events.programme_locks import fences, lock_event, event_scopes, lock_authority
    from .admission_bridge import CanonicalRegistrationBridge
    install(AdmissionIntegrations(registration=CanonicalRegistrationBridge(), fences=fences,
        lock_event=lock_event, event_scopes=event_scopes, lock_actor=lock_authority, **providers))
