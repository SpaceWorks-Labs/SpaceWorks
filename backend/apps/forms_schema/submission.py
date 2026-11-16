"""F's single v1/v2 member-input validator. P alone resolves encrypted DOB.

The result is an in-process value, never a client authority flag. Domain services
recheck current subject/schema/date fences and bind P's persisted derivation IDs.
"""
from django.utils.translation import gettext
from copy import deepcopy
from dataclasses import dataclass, field
from django.core.exceptions import ValidationError as SchemaError
from rest_framework.exceptions import APIException, ValidationError
from .answers_v2 import normalize_answer, unanswered
from .conditions import visible
from .profile_fields import PROFILE_FIELDS, ProfileValueError, normalize_dob, normalize_profile_value
from .schema_v2 import validate_schema
from .sensitive_policy import validate_context
from .file_values import resolve_files


def error(code, fields=None, detail="Invalid answer."):
    raise ValidationError({"code": code, "detail": detail, "fields": fields or {}})


class FormContextConflict(APIException):
    status_code = 409

    def __init__(self, code, detail, **context):
        super().__init__({"code": code, "detail": detail, "fields": {}, **context})


@dataclass(frozen=True)
class ValidatedForm:
    schema: object = field(repr=False)
    _snapshot: object = field(repr=False)
    visible_question_ids: tuple[str, ...]
    omitted_question_ids: tuple[str, ...]
    profile_values: dict = field(repr=False)
    save_choices: dict
    saved_detail_versions: dict
    derivations: dict = field(repr=False)
    subject: object = None

    @property
    def snapshot(self):
        if self.derivations:
            error("derivation_preparation_required", detail="Bind server-owned derivations before storing answers.")
        return deepcopy(self._snapshot)

    def snapshot_with_derivations(self, derivation_ids):
        if set(derivation_ids) != set(self.derivations) or any(
            type(value) is not int or value < 1 for value in derivation_ids.values()
        ):
            error("derivation_preparation_required")
        result = deepcopy(self._snapshot)
        rows = {answer["id"]: answer for answer in result["answers"]}
        for question in self.schema["questions"]:
            qid = question["id"]
            if qid in derivation_ids:
                rows[qid] = {"id": qid, "label": question["label"], "type": "age_at_event",
                             "derivation_id": derivation_ids[qid]}
        result["answers"] = [rows[qid] for qid in self.visible_question_ids if qid in rows]
        return result

    @property
    def explicit_dob_values(self):
        """P compares these to a resolved saved DOB source before any mutation."""
        return tuple(row["value"] for row in (self._snapshot or {}).get("answers", [])
                     if row["type"] == "date_of_birth")


def _derivation(value):
    if not isinstance(value, dict) or set(value) != {"source", "reviewed_event_date_revision", "reviewed_as_of_date"}:
        error("invalid_derivation")
    source = value["source"]
    if not isinstance(source, dict):
        error("invalid_derivation")
    if source.get("kind") == "inline_dob" and set(source) == {"kind", "date_of_birth"}:
        try:
            source = {**source, "date_of_birth": normalize_dob(source["date_of_birth"])}
        except ProfileValueError:
            error("invalid_derivation", detail="Enter a valid date of birth.")
    elif (source.get("kind") == "saved_detail" and set(source) == {"kind", "field_key", "version"}
          and source["field_key"] == "date_of_birth" and type(source["version"]) is int and source["version"] > 0):
        source = dict(source)
    else:
        error("invalid_derivation")
    from datetime import date
    try:
        date.fromisoformat(value["reviewed_as_of_date"])
    except (TypeError, ValueError):
        error("invalid_derivation")
    if type(value["reviewed_event_date_revision"]) is not int or value["reviewed_event_date_revision"] < 1:
        error("invalid_derivation")
    return {**value, "source": source}


def _saves(payload, mapped, derivations, sensitive_keys=()):
    choices, versions = payload.get("save_choices", {}), payload.get("saved_detail_versions", {})
    if not isinstance(choices, dict) or not isinstance(versions, dict):
        error("invalid_save_choices")
    allowed = {key for key, item in PROFILE_FIELDS.items() if item.persistable}
    if (set(choices) - allowed or set(versions) - allowed or any(type(v) is not bool for v in choices.values())
            or any(type(v) is not int or v < 0 for v in versions.values())):
        error("invalid_save_choices")
    # Inline DOB is never a numeric age answer. P resolves saved-detail sources.
    sources = [item["source"] for item in derivations.values()]
    inline = {item["date_of_birth"] for item in sources if item["kind"] == "inline_dob"}
    if len(inline) > 1 or (inline and "date_of_birth" in mapped and mapped["date_of_birth"] not in inline):
        error("dob_source_mismatch")
    if inline:
        mapped["date_of_birth"] = next(iter(inline))
    if sources and "date_of_birth" not in mapped:
        # This marker is resolved to owner's DOB by P before any intent preparation.
        mapped["date_of_birth"] = sources[0]
    effective = {key: choices.get(key, PROFILE_FIELDS[key].default_save and key not in sensitive_keys) for key in mapped}
    for key, save in choices.items():
        if save and key not in mapped:
            error("invalid_save_choices", {key: ["Only visible answered fields can be saved."]})
    for key, save in effective.items():
        if save and key not in versions:
            error("saved_version_required", {key: ["Supply the current saved version (0 if new)."]})
    return effective, {key: versions[key] for key in effective if key in versions}


def validate_submission(*, schema, payload, subject=None, context=None, file_resolver=None):
    if not isinstance(payload, dict):
        error("invalid_form_input")
    if context == "stage" and payload.get("derivations"):
        error("stage_age_question_unsupported", detail="Stage forms do not support DOB or age derivations.")
    if not isinstance(schema, dict):
        from .legacy import validate_answers
        snapshot = validate_answers(schema, payload.get("answers"))
        return ValidatedForm(schema, snapshot, tuple(q["id"] for q in (schema or [])), (), {}, {}, {}, {}, subject)
    try:
        schema = validate_schema(schema, context=context)
        validate_context(schema, context=context, derivations=payload.get("derivations"))
    except SchemaError as exc:
        code = getattr(exc, "code", None) or "invalid_form_schema"
        error(code, detail=" ".join(exc.messages))
    if subject is not None and "form" not in payload:
        error("invalid_form_input", {"form": ["This field is required."]})
    if "form" in payload:
        form = payload["form"]
        if (not isinstance(form, dict) or set(form) != {"schema_version", "form_id", "revision"}
                or type(form["schema_version"]) is not int or type(form["revision"]) is not int
                or not isinstance(form["form_id"], str)):
            error("invalid_form_input", {"form": ["Use the matching form descriptor."]})
    if "form" in payload and payload["form"] != {"schema_version": 2, "form_id": schema["form_id"], "revision": schema["revision"]}:
        raise FormContextConflict("form_revision_changed", gettext("Review the current form revision."), form={
            "schema_version": 2, "form_id": schema["form_id"], "revision": schema["revision"]})
    event_context = schema.get("event_context")
    if (event_context and "event_date_revision" in payload
            and (type(payload["event_date_revision"]) is not int
                 or payload["event_date_revision"] != event_context["event_date_revision"])):
        raise FormContextConflict("event_date_changed", gettext("Review the revised event date."),
                                  event_date_revision=event_context["event_date_revision"])
    raw, sources = payload.get("answers"), payload.get("derivations", {})
    if raw is None:
        raw = {}
    if not isinstance(raw, dict) or not isinstance(sources, dict):
        error("invalid_form_input")
    ids = {question["id"] for question in schema["questions"]}
    unknown = (set(raw) | set(sources)) - ids
    if unknown:
        error("invalid_answer", {key: ["Unknown question ID."] for key in unknown})
    values, mapped, answers, derivations, shown, omitted, errors = {}, {}, [], {}, [], [], {}
    for question in schema["questions"]:
        qid, kind = question["id"], question["type"]
        if question.get("visibility") == "server" or not visible(question.get("show_if"), values):
            omitted.append(qid)
            continue
        shown.append(qid)
        if kind == "age_at_event":
            if qid in raw:
                error("derived_value_not_accepted", {qid: ["Supply a private DOB source in derivations."]})
            if qid in sources:
                derivations[qid] = _derivation(sources[qid])
            elif question["required"]:
                errors[qid] = ["This question is required."]
            continue
        if qid in sources:
            error("invalid_derivation", {qid: ["Only derived questions accept derivations."]})
        value = raw.get(qid)
        if unanswered(value):
            if question["required"]:
                errors[qid] = ["This question is required."]
            continue
        try:
            value = normalize_answer(question, value)
            if value is None or value == {"option_ids": []} or value == []:
                if question["required"]:
                    errors[qid] = ["This question is required."]
                continue
            if kind == "file":
                resolve_files(question, value, file_resolver)
            key = question.get("profile_field_key")
            if key:
                profile_value = value.get("option_id", value.get("option_ids")) if kind in {"single_choice", "multi_choice"} else value
                profile_value = normalize_profile_value(key, profile_value)
                if key in mapped and mapped[key] != profile_value:
                    error("duplicate_profile_mapping", {qid: ["Mapped answers must agree."]})
                mapped[key] = profile_value
        except ProfileValueError as exc:
            errors[qid] = exc.fields if exc.fields is not None else [str(exc)]
            continue
        values[qid] = value
        answers.append({"id": qid, "label": question["label"], "type": kind, "value": value,
                        **({"sensitive": True} if question.get("sensitive") else {})})
    if errors:
        error("invalid_answer", errors)
    context = schema.get("event_context")
    if derivations and context:
        if subject is not None and getattr(subject, "event_id", None) != context["event_id"]:
            error("invalid_form_context")
        for derivation in derivations.values():
            if (payload.get("event_date_revision", context["event_date_revision"]) != context["event_date_revision"]
                    or derivation["reviewed_event_date_revision"] != context["event_date_revision"]
                    or derivation["reviewed_as_of_date"] != context["as_of_date"]):
                raise FormContextConflict("event_date_changed", gettext("Review age at the revised event start."),
                    event_date_revision=context["event_date_revision"], as_of_date=context["as_of_date"])
    explicit_dobs = {row["value"] for row in answers if row["type"] == "date_of_birth"}
    inline_dobs = {item["source"]["date_of_birth"] for item in derivations.values()
                   if item["source"]["kind"] == "inline_dob"}
    if len(explicit_dobs | inline_dobs) > 1:
        error("dob_source_mismatch")
    sensitive_keys = {q.get("profile_field_key") for q in schema["questions"] if q.get("sensitive")}
    effective, versions = _saves(payload, mapped, derivations, sensitive_keys)
    snapshot = {"version": 2, "form_id": schema["form_id"], "form_revision": schema["revision"], "answers": answers}
    return ValidatedForm(schema, snapshot, tuple(shown), tuple(omitted), mapped, effective, versions, derivations, subject)
