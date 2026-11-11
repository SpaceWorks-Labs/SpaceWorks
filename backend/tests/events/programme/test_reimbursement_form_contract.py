"""F-add-on executable contract: pure validators; domain attachment stays in R.

The literal fixtures below are the F handoff to G's shared reimbursement_addon.json.
Currency cases intentionally exercise G's real shared helper once integrated.
"""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError as SchemaError
from rest_framework.exceptions import ValidationError

from apps.forms_schema.schema_v2 import validate_schema, form_features
from apps.forms_schema.submission import validate_submission, FormContextConflict
from apps.forms_schema.validation import validate_answers, validate_form_schema
from apps.forms_schema.prefill import prefill_for_schema
from apps.forms_schema.sensitive_policy import project_answers, project_schema
from apps.forms_schema.profile_fields import PROFILE_FIELDS


def question(kind="short_text", **extra):
    return {"id": "q", "type": kind, "label": "Question", "required": False, **extra}


def schema(*questions):
    return {"schema_version": 2, "form_id": "travel", "revision": 1, "questions": list(questions)}


FILE_REF = {"asset_id": 91, "generation": 1, "sha256": "a" * 64}
STAGE_SCHEMA = schema(question("file", file={"purpose": "stage_form_file", "max_files": 5,
                                            "max_bytes_each": 10485760}))
CLAIM_SCHEMA = schema(
    question("money", id="estimate", required=True,
             money={"currencies": ["INR"], "min_minor": 0, "max_minor": 10000000}),
    question("itinerary", id="journey", sensitive=True,
             itinerary={"modes": ["rail", "air", "bus", "car", "other"]}),
    question("file", id="receipt", required=True, sensitive=True,
             file={"purpose": "reimbursement_receipt", "max_files": 5, "max_bytes_each": 10485760}),
)
CLAIM_INPUT = {
    "form": {"schema_version": 2, "form_id": "travel", "revision": 1},
    "answers": {"estimate": {"amount_minor": 125000, "currency": "INR"},
                "journey": {"mode": "rail", "origin": " Kochi ", "destination": "Bengaluru",
                            "depart_at": "2026-12-01T12:00:00Z", "arrive_at": "2026-12-02T01:00:00Z"},
                "receipt": [FILE_REF]},
    "derivations": {}, "save_choices": {}, "saved_detail_versions": {}, "event_date_revision": 1,
}
# Frozen v1 lists/map spelling and canonical snapshot must remain byte-compatible.
V1_SCHEMA = [{"id": "count", "type": "number", "label": "People", "required": True, "options": []},
             {"id": "yes", "type": "yes_no", "label": "Joining", "required": True, "options": []}]
V1_INPUT = {"count": "2", "yes": False}
V1_SNAPSHOT = {"version": 1, "answers": [
    {"id": "count", "type": "number", "label": "People", "value": 2},
    {"id": "yes", "type": "yes_no", "label": "Joining", "value": False}]}


def test_v1_compatibility_fixture_and_unchanged_raw_alias():
    from apps.events.registration_form_adapter import normalize_registration_input
    assert validate_form_schema(V1_SCHEMA) == V1_SCHEMA
    assert validate_answers(V1_SCHEMA, V1_INPUT) == V1_SNAPSHOT
    normalized = normalize_registration_input({"custom_answers": V1_INPUT}, schema_version=1)
    assert validate_submission(schema=V1_SCHEMA, payload=normalized.payload).snapshot == V1_SNAPSHOT
    with pytest.raises(ValidationError):
        normalize_registration_input({"answers": V1_INPUT}, schema_version=1)


@pytest.mark.parametrize("currency", ["INR", " inr ", "JPY", "KWD"])
def test_money_uses_shared_currency_contract(currency):
    form = schema(question("money", money={"currencies": [currency], "max_minor": 100}))
    result = validate_answers(form, {"q": {"amount_minor": 1, "currency": currency}})
    assert result["answers"][0]["value"] == {"amount_minor": 1, "currency": currency.strip().upper()}


@pytest.mark.parametrize("amount", [True, 1.0, "1", "1e2", -1, 101, 9007199254740992])
def test_money_never_coerces_numbers(amount):
    form = schema(question("money", money={"currencies": ["INR"], "max_minor": 100}))
    with pytest.raises(ValidationError):
        validate_answers(form, {"q": {"amount_minor": amount, "currency": "INR"}})


def test_money_unknown_and_unconfigured_currency_and_arbitrary_json_refused():
    for currencies in (["ZZZ"], ["INR", " inr "]):
        with pytest.raises(SchemaError):
            validate_schema(schema(question("money", money={"currencies": currencies})))
    form = schema(question("money", money={"currencies": ["INR"]}))
    for raw in ({"amount_minor": 1, "currency": "JPY"}, {"amount_minor": 1, "currency": "INR", "rate": 1}):
        with pytest.raises(ValidationError):
            validate_answers(form, {"q": raw})


def test_claim_fixture_preserves_map_envelope_and_authorizes_each_reference():
    checked = []
    result = validate_submission(schema=CLAIM_SCHEMA, payload=CLAIM_INPUT, context="claim",
        file_resolver=lambda **kwargs: checked.append(kwargs) is None)
    assert result.profile_values == {} and result.derivations == {} and result.save_choices == {}
    assert checked[0]["reference"] == FILE_REF
    assert result.snapshot["answers"][1]["value"]["origin"] == "Kochi"
    assert form_features(result.schema) == ["file", "itinerary", "money", "sensitive"]
    with pytest.raises(ValidationError):
        validate_submission(schema=CLAIM_SCHEMA, payload={"answers": result.snapshot["answers"]}, context="claim")


@pytest.mark.parametrize("purpose", ["reimbursement_receipt", "reimbursement_payee_document"])
@pytest.mark.parametrize("context", [None, "stage"])
def test_generic_and_stage_contexts_reject_finance_purposes_even_hidden(purpose, context):
    form = schema(question("file", sensitive=True, visibility="server", file={
        "purpose": purpose, "max_files": 1, "max_bytes_each": 100}))
    with pytest.raises(SchemaError) as caught:
        validate_schema(form, context=context)
    assert caught.value.code == "file_purpose_not_allowed"


@pytest.mark.parametrize("context,purpose", [("stage", "stage_form_file"), ("claim", "reimbursement_receipt"),
                                            ("payee", "reimbursement_payee_document")])
def test_only_matching_context_and_domain_authorized_file_references(context, purpose):
    form = schema(question("file", sensitive=context != "stage", file={
        "purpose": purpose, "max_files": 1, "max_bytes_each": 100}))
    result = validate_submission(schema=form, payload={"answers": {"q": [FILE_REF]}}, context=context,
                                 file_resolver=lambda **kwargs: True)
    assert result.snapshot["answers"][0]["value"] == [FILE_REF]
    for resolver in (None, lambda **kwargs: False):
        with pytest.raises(ValidationError):
            validate_submission(schema=form, payload={"answers": {"q": [FILE_REF]}}, context=context,
                                file_resolver=resolver)


@pytest.mark.parametrize("reference", [{**FILE_REF, "generation": True}, {**FILE_REF, "sha256": "bad"},
    {**FILE_REF, "asset_id": -1}, {**FILE_REF, "object_key": "private"}, {"url": "https://example.test"}])
def test_file_reference_boundaries(reference):
    with pytest.raises(ValidationError):
        validate_submission(schema=STAGE_SCHEMA, payload={"answers": {"q": [reference]}}, context="stage",
                            file_resolver=lambda **kwargs: True)


def test_hidden_files_never_resolve_attach_or_save_and_empty_required_file_refused():
    form = schema(question("yes_no", id="has"), {**STAGE_SCHEMA["questions"][0], "required": True,
        "show_if": {"field_id": "has", "op": "eq", "value": True}})
    def forbidden(**kwargs):
        pytest.fail("A hidden file must never reach its domain adapter")
    result = validate_submission(schema=form, payload={"answers": {"has": False, "q": [{"bad": True}]}},
                                 context="stage", file_resolver=forbidden)
    assert result.omitted_question_ids == ("q",) and result.profile_values == {}
    with pytest.raises(ValidationError):
        validate_submission(schema=form, payload={"answers": {"has": True, "q": []}}, context="stage")


@pytest.mark.parametrize("extra", [{"type": "date_of_birth"}, {"type": "age_at_event"},
    {"type": "date", "profile_field_key": "date_of_birth"}, {"derivation_binding": "age"}])
def test_stage_publication_prefill_and_submit_reject_age_even_optional_hidden_sensitive(extra):
    form = schema(question(visibility="server", sensitive=True, **extra))
    for check in (lambda: validate_schema(form, context="stage"),
                  lambda: prefill_for_schema(form, {}, context="stage")):
        with pytest.raises(SchemaError) as caught:
            check()
        assert caught.value.code == "stage_age_question_unsupported"
    with pytest.raises(ValidationError) as caught:
        validate_submission(schema=form, payload={"answers": {}}, context="stage")
    assert caught.value.detail["code"] == "stage_age_question_unsupported"


def test_stage_rejects_nonempty_derivations_and_base_form_derivation_stays_unchanged():
    with pytest.raises(ValidationError, match="stage_age_question_unsupported"):
        validate_submission(schema=schema(), payload={"answers": {}, "derivations": {"age": {}}}, context="stage")
    source = {"source": {"kind": "inline_dob", "date_of_birth": "2000-01-01"},
              "reviewed_event_date_revision": 1, "reviewed_as_of_date": "2026-12-01"}
    result = validate_submission(schema=schema(question("age_at_event")),
                                 payload={"answers": {}, "derivations": {"q": source}})
    assert result.derivations == {"q": source}
    assert result.snapshot_with_derivations({"q": 1})["answers"][0]["derivation_id"] == 1


def test_itinerary_normalization_nulls_timezone_and_bounds():
    form = schema(question("itinerary", itinerary={"modes": ["rail"]}))
    result = validate_answers(form, {"q": {"mode": "rail", "origin": " Kochi ",
        "depart_at": "2026-12-01T17:30:00+05:30", "arrive_at": "2026-12-01T12:00:00Z"}})
    assert result["answers"][0]["value"] == {"mode": "rail", "origin": "Kochi", "destination": None,
        "depart_at": "2026-12-01T12:00:00Z", "arrive_at": "2026-12-01T12:00:00Z"}
    for value in ({"mode": "rail", "depart_at": "2026-12-01T12:00:00"},
                  {"mode": "rail", "depart_at": "2026-12-02T12:00:00Z", "arrive_at": "2026-12-01T12:00:00Z"},
                  {"mode": "rail", "origin": "a" * 201}, {"mode": "rail", "origin": ""},
                  {"mode": "air"}, {"mode": "rail", "timezone": "UTC"}):
        with pytest.raises(ValidationError):
            validate_answers(form, {"q": value})


def test_sensitive_save_opt_in_and_no_payee_profile_registry_keys():
    form = schema(question(profile_field_key="name", sensitive=True))
    payload = {"answers": {"q": "Member"}}
    result = validate_submission(schema=form, payload=payload)
    assert result.save_choices == {"name": False}
    assert prefill_for_schema(form, {"name": "Member"}) == ({"q": "Member"}, {"name": False})
    with pytest.raises(ValidationError, match="saved_version_required"):
        validate_submission(schema=form, payload={**payload, "save_choices": {"name": True}})
    saved = validate_submission(schema=form, payload={**payload, "save_choices": {"name": True},
        "saved_detail_versions": {"name": 0}})
    assert saved.saved_detail_versions == {"name": 0}
    assert not set(PROFILE_FIELDS) & {"iban", "bank_account", "upi", "payee", "itinerary"}


def test_sensitive_disclosure_and_conditional_leaks_refused():
    with pytest.raises(SchemaError, match="Sensitive answers"):
        validate_schema(schema(question(sensitive=True, disclosure={"organizer": True, "reviewer": False, "judge": False})))
    with pytest.raises(SchemaError) as caught:
        validate_schema(schema(question("yes_no", id="private", sensitive=True),
            question(show_if={"field_id": "private", "op": "is_set"})))
    assert caught.value.code == "sensitive_condition_forbidden"


def test_authorized_projection_intersects_current_and_pinned_disclosure_and_omits_files_without_adapter():
    form = validate_schema(schema(question(id="public"), question(id="secret", sensitive=True),
        question("file", id="file", file={"purpose": "stage_form_file", "max_files": 1, "max_bytes_each": 100})), context="stage")
    snapshot = validate_submission(schema=form, payload={"answers": {"public": "Open", "secret": "Private", "file": [FILE_REF]}},
        context="stage", file_resolver=lambda **kwargs: True).snapshot
    assert [row["id"] for row in project_answers(form, snapshot, viewer="organizer")["answers"]] == ["public"]
    assert [row["id"] for row in project_answers(form, snapshot, viewer="finance")["answers"]] == ["secret"]
    assert project_answers(form, snapshot, viewer="export")["answers"] == []
    current = deepcopy(form)
    current["questions"][0]["sensitive"] = True
    assert project_answers(form, snapshot, viewer="organizer", current_schema=current)["answers"] == []
    assert project_schema(form, viewer="finance", current_schema=current)["questions"][0]["sensitive"] is True
    current["questions"] = []
    assert project_answers(form, snapshot, viewer="finance", current_schema=current)["answers"] == []


def test_stage_descriptor_date_conflict_and_snapshot_array_rejection():
    form = schema(question())
    form["event_context"] = {"event_id": 1, "event_date_revision": 2, "timezone_name": "UTC", "as_of_date": "2026-12-01"}
    payload = {"form": {"schema_version": 2, "form_id": "travel", "revision": 1}, "answers": {"q": "Text"},
               "event_date_revision": 2, "derivations": {}}
    result = validate_submission(schema=form, payload=payload, context="stage", subject=SimpleNamespace(event_id=1))
    assert result.derivations == {}
    for patch in ({"event_date_revision": 1}, {"form": {**payload["form"], "revision": 2}}):
        with pytest.raises(FormContextConflict):
            validate_submission(schema=form, payload={**payload, **patch}, context="stage")
    with pytest.raises(ValidationError):
        validate_submission(schema=form, payload={**payload, "answers": result.snapshot["answers"]}, context="stage")


def test_stage_model_selector_and_provider_contract(monkeypatch):
    from apps.events.programme.form_models import EventFormRevision
    from apps.events.programme import providers
    assert ("stage", "stage") in EventFormRevision._meta.get_field("form_key").choices
    assert ("stage", "stage") in EventFormRevision._meta.get_field("selector_kind").choices
    monkeypatch.setattr(providers, "_forms", {})
    provider = providers.FormProvider("stage", lambda **kw: None, lambda **kw: None, lambda **kw: None)
    providers.register_form(provider)
    assert providers.form_provider("stage") is provider


def test_stage_revision_saver_checks_context_and_cas_then_appends_with_audit(monkeypatch):
    from unittest.mock import Mock
    from django import db
    from apps.audit import services as audit
    from apps.events import event_authority
    from apps.events.programme.form_models import EventFormRevision
    from apps.events.programme.providers import append_stage_revision_locked
    from rest_framework.exceptions import NotFound

    event = SimpleNamespace(pk=3, makerspace=object())
    target = SimpleNamespace(pk=5, event_id=3, form_id="travel", current_revision_id=None)
    actor, authority, record = object(), Mock(), Mock()
    history = Mock()
    history.using.return_value = history
    latest = history.filter.return_value.order_by.return_value.first
    latest.return_value = None
    history.create.side_effect = lambda **values: SimpleNamespace(pk=70, **values)
    connection = SimpleNamespace(in_atomic_block=True)
    monkeypatch.setattr(db, "connections", {"default": connection})
    monkeypatch.setattr(db.router, "db_for_write", lambda *args, **kwargs: "default")
    monkeypatch.setattr(EventFormRevision, "objects", history)
    monkeypatch.setattr(event_authority, "require", authority)
    monkeypatch.setattr(audit, "record", record)

    first = append_stage_revision_locked(event=event, actor=actor, target=target, schema=STAGE_SCHEMA)
    assert first.revision == 1 and first.selector_kind == "stage" and first.selector_id == 5
    authority.assert_called_with(actor, event, "edit_details")
    assert record.call_args.kwargs["meta"]["revision_id"] == 70
    latest.return_value, target.current_revision_id = first, first.pk
    second = append_stage_revision_locked(event=event, actor=actor, target=target, schema=first.schema)
    assert second.revision == 2 and first.schema["revision"] == 1
    with pytest.raises(FormContextConflict):
        append_stage_revision_locked(event=event, actor=actor, target=target,
                                     schema={**STAGE_SCHEMA, "revision": 3})
    with pytest.raises(NotFound):
        append_stage_revision_locked(event=event, actor=actor, target=SimpleNamespace(pk=5, event_id=99), schema=STAGE_SCHEMA)
    connection.in_atomic_block = False
    with pytest.raises(RuntimeError):
        append_stage_revision_locked(event=event, actor=actor, target=target, schema=STAGE_SCHEMA)
    assert history.create.call_count == 2 and record.call_count == 2
