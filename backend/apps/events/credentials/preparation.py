"""Command-scoped credential material prepared before ordered domain locks."""
from django.utils.translation import gettext
from contextlib import contextmanager
from contextvars import ContextVar

from .errors import CredentialKeyUnavailable, ProgrammeConflict
from apps.transaction_guards import in_domain_transaction

_held = ContextVar("prepared_event_credentials", default=None)


@contextmanager
def prepare_event_credentials(event_ids):
    from apps.events.models_registration import EventRegistration
    from .workflow import prepare_issue
    event_ids = tuple(sorted(set(event_ids)))
    held = _held.get()
    if held is not None:
        if not set(event_ids) <= held.keys():
            raise ProgrammeConflict(gettext("Credential preparation scope changed."))
        yield
        return
    if in_domain_transaction():
        raise RuntimeError("Prepare credential material before domain locks.")
    values = {}
    for event_id in event_ids:
        candidate = EventRegistration()
        candidate._reserve_pk()
        ids = list(EventRegistration.objects.filter(event_id=event_id).values_list("pk", flat=True))
        prepared = {}
        for pk in [*ids, candidate.pk]:
            try:
                prepared[pk] = prepare_issue(event_id, pk)
            except CredentialKeyUnavailable as exc:
                # A date/answer/cancel command never needs issuance. Keep key failure
                # until a command actually attempts to grant admission; that rolls back.
                prepared[pk] = exc
        values[event_id] = (candidate.pk, prepared)
    token = _held.set(values)
    try:
        yield
    finally:
        _held.reset(token)


def new_registration_id(event_id):
    held = _held.get()
    if held is None or event_id not in held:
        raise RuntimeError("Prepare a new canonical registration before event locks.")
    return held[event_id][0]


def prepared_issue(event_id, registration_id):
    held = _held.get()
    if held is None or event_id not in held or registration_id not in held[event_id][1]:
        raise ProgrammeConflict(gettext("Prepare the registration credential before event locks."))
    prepared = held[event_id][1][registration_id]
    if isinstance(prepared, CredentialKeyUnavailable):
        raise prepared
    return prepared
