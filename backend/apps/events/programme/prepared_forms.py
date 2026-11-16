"""F validation and P preparation shared by ordinary, application and role forms.

Only ciphertext and canonical source references cross into the event transaction.
The temporary binding below is internal process state, never browser input.
"""
from django.utils.translation import gettext
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, field
from uuid import UUID
import json

from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.accounts.saved_details.intents import ValidatedSaveInput, digest, prepare_saved_detail_intent
from apps.accounts.saved_details.subject_binding import VerifiedIntentBinding
from apps.events.answer_derivations.preparation import prepare_derivations, source_dob
from apps.events.answer_derivations.subjects import require_member, require_owner
from apps.events.hackathons.api_context import form_descriptor
from apps.forms_schema.submission import validate_submission

_binding = ContextVar("validated_event_save_binding", default=None)


@dataclass(frozen=True)
class PreparedForm:
    subject: object
    schema: object = field(repr=False)
    snapshot: dict = field(repr=False)
    form_sha256: str
    answer_sha256: str
    event_date_revision: int
    saved_intent: object = field(default=None, repr=False)
    derivations: object = field(default=None, repr=False)
    omitted_question_ids: tuple = ()
    consent_revision: int | None = None
    # (validated input, choices, versions) of an explicit save, for cross-form conflict checks.
    save_check: tuple | None = field(default=None, repr=False)


def saved_dob(*, actor_id, version):
    from apps.accounts.saved_details.models import MemberSavedDetail
    from apps.accounts.saved_details.crypto import open_value
    require_member(actor_id)
    row = MemberSavedDetail.objects.filter(user_id=actor_id, field_key="date_of_birth",
        version=version, deleted_at__isnull=True).first()
    if row is None:
        raise ValidationError({"code": "saved_detail_changed", "fields": {"date_of_birth": [gettext("Review saved details.")]}})
    return open_value(row, "value_envelope")


def prepare(*, actor_id, subject, schema, payload, submit=True, previous_answers=None):
    from apps.events.models_event import Event
    event = Event.objects.select_related("makerspace").get(pk=subject.event_id)
    require_member(actor_id)
    if subject.owner_member_id != actor_id:
        from rest_framework.exceptions import NotFound
        raise NotFound()
    reopening = False
    if subject.subject_id:
        require_owner(actor_id, subject)
        from apps.events.answer_derivations.subjects import resolve_subject
        reopening = subject.kind.value == "application" and resolve_subject(subject).state in (
            "rejected", "declined", "expired", "withdrawn")
    original = form_descriptor(event, schema or [])
    if not isinstance(payload, dict):
        raise ValidationError({"code": "invalid_form_payload", "fields": {"form": [gettext("Use an object.")]}})
    validation_schema, data = deepcopy(original), deepcopy(payload)
    for key in ("answers", "derivations", "save_choices", "coc"):
        if key in data and not isinstance(data[key], dict):
            raise ValidationError({"code": "invalid_form_payload", "fields": {key: [gettext("Use an object.")]}})
    from apps.forms_schema.profile_fields import PROFILE_FIELDS
    supplied_choices = data.get("save_choices", {})
    if isinstance(supplied_choices, dict):
        data["save_choices"] = {**{key: False for key, info in PROFILE_FIELDS.items() if info.persistable},
                                **supplied_choices}
    if "custom_answers" in data:
        raise ValidationError({"code": "answer_field_conflict", "fields": {"custom_answers": [gettext("Use answers.")]}})
    if previous_answers:
        prior = json.loads(previous_answers) if isinstance(previous_answers, str) else previous_answers
        questions = original.get("questions", []) if isinstance(original, dict) else (original or [])
        current_ids = {row["id"] for row in questions}
        values = {row["id"]: row["value"] for row in prior.get("answers", [])
                  if "value" in row and row["id"] in current_ids}
        data["answers"] = {**values, **data.get("answers", {})}
        from apps.events.answer_derivations.models import EventAnswerDerivation
        from apps.events.answer_derivations.subjects import subject_filter
        from apps.events.answer_derivations.crypto import decrypt_source
        prior_sources = {row["id"]: row for row in prior.get("answers", [])
                         if row.get("type") == "age_at_event" and row["id"] in current_ids}
        data.setdefault("derivations", {})
        for question_id, descriptor in prior_sources.items():
            if question_id in data["derivations"]:
                continue
            source = EventAnswerDerivation.objects.filter(**subject_filter(subject), question_id=question_id,
                pk=descriptor["derivation_id"]).first()
            if source:
                data["derivations"][question_id] = {"source": {"kind": "inline_dob", "date_of_birth": decrypt_source(source)},
                    "reviewed_event_date_revision": source.event_date_revision,
                    "reviewed_as_of_date": source.as_of_date.isoformat()}
    if not submit:
        questions = validation_schema.get("questions", []) if isinstance(validation_schema, dict) else validation_schema
        for question in questions or []:
            question["required"] = False
        data["save_choices"] = {key: False for key in data.get("save_choices", {})}
    validated = validate_submission(schema=validation_schema, payload=data, subject=subject)
    # Draft validation relaxes requiredness only; bind the actual authored schema.
    form_hash = digest(original)
    provisional = validated.snapshot_with_derivations({qid: 1 for qid in validated.derivations}) if validated.derivations else validated.snapshot
    if provisional is None:
        provisional = {"version": 2, "answers": []}
    sources = prepare_derivations(actor_id=actor_id, subject=subject, derivations=validated.derivations,
        visible_question_ids=validated.visible_question_ids, form_sha256=form_hash,
        canonical_answer_sha256=digest(provisional), saved_dob_loader=saved_dob,
        explicit_dob=(validated.explicit_dob_values or (None,))[0], reopening=reopening)
    snapshot = validated.snapshot_with_derivations({s.question_id: s.pk for s in sources.sources}) if sources else provisional
    # Source preparation and saved intent must bind the same final canonical IDs.
    if sources:
        from dataclasses import replace
        sources = replace(sources, canonical_answer_sha256=digest(snapshot))
    mapped = dict(validated.profile_values)
    if isinstance(mapped.get("date_of_birth"), dict):
        mapped["date_of_birth"] = source_dob({"kind": "saved_detail", **mapped["date_of_birth"]},
            actor_id=actor_id, saved_dob_loader=saved_dob).isoformat()
    saved = save_check = None
    choices = {key: bool(payload.get("save_choices", {}).get(key, False)) for key in mapped}
    if submit and any(choices.values()):
        save_input = ValidatedSaveInput(subject=subject, mapped_values=mapped,
            canonical_answers=snapshot, form_descriptor=original, event_date_revision=event.event_date_revision)
        save_check = (save_input, choices, validated.saved_detail_versions)
        saved = prepare_saved_detail_intent(actor_id=actor_id, subject=subject, validated_form=save_input,
            choices=choices, base_versions=validated.saved_detail_versions,
            operation_id=UUID(str(payload["operation_id"])))
    coc = payload.get("coc") or {}
    consent = coc.get("revision") if coc.get("accepted") is True else None
    return PreparedForm(subject, original, snapshot, form_hash, digest(snapshot), event.event_date_revision,
        saved, sources, validated.omitted_question_ids, consent, save_check)


def require_current(prepared, event, schema):
    from apps.forms_schema.submission import FormContextConflict
    if digest(form_descriptor(event, schema or [])) != prepared.form_sha256:
        raise FormContextConflict("form_revision_changed", gettext("Review the current form."))
    if event.event_date_revision != prepared.event_date_revision:
        raise FormContextConflict("event_date_changed", gettext("Review the current event date."))


def apply_locked(prepared, *, subject, locks, store_intent=True):
    from apps.events.programme_locks import assert_lock_context
    from apps.events.answer_derivations.workflow import insert_prepared_locked
    from apps.accounts.saved_details.intents import insert_prepared_locked as insert_intent
    assert_lock_context(locks)
    require_owner(subject.owner_member_id, subject)
    prior = prepared.subject
    if (prior.event_id, prior.owner_member_id, prior.kind) != (subject.event_id, subject.owner_member_id, subject.kind):
        raise ValidationError({"code": "invalid_subject"})
    if prior.subject_id is not None and prior.subject_id != subject.subject_id:
        raise ValidationError({"code": "invalid_subject"})
    from .draft_sources import prune_answer_sources_locked
    prune_answer_sources_locked(subject=subject, snapshot=prepared.snapshot, locks=locks)
    insert_prepared_locked(prepared.derivations, actor_id=subject.owner_member_id,
        subject=subject, locks=locks, form_sha256=prepared.form_sha256,
        canonical_answer_sha256=prepared.answer_sha256, creation_operation_id=prior.creation_operation_id)
    intent_id = None
    if store_intent and prepared.saved_intent:
        token = _binding.set((prepared, subject, locks))
        try:
            intent_id = insert_intent(prepared.saved_intent, subject=subject, locks=locks)
        finally:
            _binding.reset(token)
    return deepcopy(prepared.snapshot), intent_id


class EventIntentBinding:
    def require_binding(self, *, prepared_subject, actual_subject, operation_id, locks):
        current = _binding.get()
        if current is None:
            raise ValidationError({"code": "invalid_subject"})
        prepared, actual, held = current
        if actual != actual_subject or held != locks or prepared.subject != prepared_subject:
            raise ValidationError({"code": "invalid_subject"})
        require_owner(actual.owner_member_id, actual)
        saved = prepared.saved_intent
        if saved is None or saved.operation_id != operation_id:
            raise ValidationError({"code": "invalid_subject"})
        return VerifiedIntentBinding(form_sha256=prepared.form_sha256,
            canonical_answer_sha256=prepared.answer_sha256, event_date_revision=prepared.event_date_revision,
            chosen_fields=saved.chosen_fields)


def intent_for(subject):
    from apps.accounts.saved_details.models import SavedDetailUpdateIntent
    row = SavedDetailUpdateIntent.objects.filter(user_id=subject.owner_member_id,
        event_id=subject.event_id, subject_kind=subject.kind.value, subject_id=subject.subject_id).order_by("-created_at").first()
    if row is None:
        return None
    return {"operation_id": str(row.operation_uuid), "state": row.state,
        "status_url": f"/api/v1/member/saved-details/save-intents/{row.operation_uuid}/"}
