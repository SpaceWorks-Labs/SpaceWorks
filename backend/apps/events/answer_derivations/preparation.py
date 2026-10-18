"""Short-lived in-process ciphertext prepared before entering event locks."""

from dataclasses import dataclass, field
from datetime import timedelta
import re

from django.utils import timezone

from apps.accounts.saved_details.age import validate_dob
from apps.events.contracts.subjects import AnswerSubject
from apps.events.models_event import Event

from .crypto import allocate_id, encrypt_source, prepared_key, require_preparation_boundary
from .dates import require_review, review_target
from .errors import DerivationError
from .models import EventAnswerDerivation
from .subjects import require_event, require_member, require_owner, subject_filter

_FACTORY = object()
_QUESTION = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class PreparedSource:
    question_id: str
    pk: int
    base_version: int
    envelope: str = field(repr=False)


@dataclass(frozen=True, kw_only=True)
class PreparedDerivations:
    subject: AnswerSubject
    sources: tuple[PreparedSource, ...] = field(repr=False)
    makerspace_id: int
    key_version: int = field(repr=False)
    event_date_revision: int
    as_of_date: object
    form_sha256: str
    canonical_answer_sha256: str
    expires_at: object
    _factory: object = field(repr=False)

    def __post_init__(self):
        if self._factory is not _FACTORY:
            raise TypeError("Use prepare_derivations.")


def source_dob(source, *, actor_id, saved_dob_loader):
    if not isinstance(source, dict):
        raise DerivationError("invalid_dob_source", "Use a private birth date source.")
    if source.get("kind") == "inline_dob" and set(source) == {"kind", "date_of_birth"}:
        raw = source["date_of_birth"]
    elif (source.get("kind") == "saved_detail" and set(source) == {"kind", "field_key", "version"}
          and source["field_key"] == "date_of_birth" and type(source["version"]) is int
          and source["version"] > 0 and saved_dob_loader is not None):
        raw = saved_dob_loader(actor_id=actor_id, version=source["version"])
    else:
        raise DerivationError("invalid_dob_source", "Use a private birth date source.")
    try:
        return validate_dob(raw)
    except ValueError as exc:
        raise DerivationError("invalid_date_of_birth", "Use a valid nonfuture birth date.") from exc


def prepare_derivations(
    *, actor_id, subject, derivations, visible_question_ids, form_sha256,
    canonical_answer_sha256, explicit_dob=None, saved_dob_loader=None,
):
    """Only server-validated visible age question IDs enter this internal API.

    A/G/C must validate the live form and subject eligibility first. A new subject
    is bound to its creation operation; insertion rechecks its real member/event.
    The loader is owner-only and returns DOB from an exact vault version.
    """
    require_preparation_boundary()
    if derivations is None or derivations == {}:
        return None  # Ordinary forms and no-vault-save remain available.
    if not isinstance(subject, AnswerSubject):
        raise TypeError("Use a typed answer subject.")
    require_member(actor_id)
    if actor_id != subject.owner_member_id:
        from rest_framework.exceptions import NotFound
        raise NotFound()
    if subject.subject_id is not None:
        require_owner(actor_id, subject)
    if not all(isinstance(value, str) and _SHA256.fullmatch(value) for value in (
        form_sha256, canonical_answer_sha256,
    )):
        raise ValueError("Bind server-computed form and canonical answer hashes.")
    if (not isinstance(derivations, dict) or len(derivations) > 50
            or any(not isinstance(q, str) or not _QUESTION.fullmatch(q) for q in derivations)
            or not set(derivations) <= set(visible_question_ids)):
        raise DerivationError("invalid_derivations", "Use visible derived questions.")
    event = Event.objects.filter(pk=subject.event_id).first()
    if event is None:
        from rest_framework.exceptions import NotFound
        raise NotFound()
    require_event(event)
    existing = list(EventAnswerDerivation.objects.filter(**subject_filter(subject))) if subject.subject_id else []
    if any(row.locked_at for row in existing):
        raise DerivationError("answers_locked", "Submitted source evidence is locked.", status=409)
    by_question = {row.question_id: row for row in existing}
    target = review_target(event, existing)
    resolved = []
    if explicit_dob is not None:
        try:
            explicit_dob = validate_dob(explicit_dob)
        except ValueError as exc:
            raise DerivationError("invalid_date_of_birth", "Use a valid nonfuture birth date.") from exc
    for question_id, item in derivations.items():
        if (not isinstance(item, dict) or set(item) != {
            "source", "reviewed_event_date_revision", "reviewed_as_of_date",
        }):
            raise DerivationError("derived_value_not_accepted", "Supply a private birth date, never a numeric age.")
        require_review(item["reviewed_event_date_revision"], item["reviewed_as_of_date"], target)
        dob = source_dob(item["source"], actor_id=actor_id, saved_dob_loader=saved_dob_loader)
        if explicit_dob is not None and dob != explicit_dob:
            raise DerivationError("dob_source_mismatch", "Use one consistent birth date source.")
        if resolved and dob != resolved[0][1]:
            raise DerivationError("dob_source_mismatch", "Use one consistent birth date source.")
        resolved.append((question_id, dob))
    version, dek = prepared_key(event.makerspace_id)
    sources = []
    for question_id, dob in resolved:
        prior = by_question.get(question_id)
        pk = prior.pk if prior else allocate_id()
        envelope = encrypt_source(dob.isoformat(), pk=pk, makerspace_id=event.makerspace_id, version=version, dek=dek)
        sources.append(PreparedSource(question_id, pk, prior.version if prior else 0, envelope))
    return PreparedDerivations(
        subject=subject, sources=tuple(sources), makerspace_id=event.makerspace_id,
        key_version=version, event_date_revision=target[0], as_of_date=target[1],
        form_sha256=form_sha256, canonical_answer_sha256=canonical_answer_sha256,
        expires_at=timezone.now() + timedelta(seconds=60), _factory=_FACTORY,
    )
