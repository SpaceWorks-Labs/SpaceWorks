from copy import deepcopy
import pytest
from rest_framework.exceptions import ValidationError
from apps.forms_schema.prefill import prefill_for_schema
from apps.forms_schema.profile_fields import normalize_profile_value
from apps.forms_schema.submission import validate_submission
from apps.forms_schema.validation import validate_answers


def schema(*questions):
    return {"schema_version": 2, "form_id": "registration", "revision": 1, "questions": list(questions)}


def question(kind="short_text", **kwargs):
    return {"id": "q", "label": "Question", "type": kind, "required": False, **kwargs}


def test_other_requires_explicit_option_and_bounded_text():
    form = schema(question("single_choice", options=[{"id": "a", "label": "A"},
        {"id": "other", "label": "Other", "other": True}], bounds={"other_max_length": 5}))
    assert validate_answers(form, {"q": {"option_id": "other", "text": " Text "}})["answers"][0]["value"] == {
        "option_id": "other", "text": "Text"}
    for value in ({"option_id": "other"}, {"option_id": "other", "text": "too long"},
                  {"option_id": "a", "text": "Text"}, "A", {"option_id": "unknown"},
                  {"option_id": "other", "other_text": "wrong key"}):
        with pytest.raises(ValidationError):
            validate_answers(form, {"q": value})


@pytest.mark.parametrize("kind,value", [("email", "bad"), ("phone", "123"), ("url", "https://user:pass@example.test/"),
    ("url", "javascript:alert(1)"), ("number", float("nan")), ("yes_no", "true"), ("date", "2026-02-29")])
def test_boundary_values_refused(kind, value):
    with pytest.raises(ValidationError):
        validate_answers(schema(question(kind)), {"q": value})


def test_blank_optional_compound_is_omitted_and_array_is_invalid():
    form = schema(question("emergency_contact", profile_field_key="emergency_contact"))
    assert validate_answers(form, {"q": {"name": "", "relationship": "", "phone": ""}})["answers"] == []
    with pytest.raises(ValidationError):
        validate_answers(form, {"q": []})
    with pytest.raises(ValidationError):
        validate_answers(form, [])


def test_duplicate_mapping_compares_canonical_values():
    form = schema(question(profile_field_key="institution"), question(id="q2", profile_field_key="institution"))
    payload = {"answers": {"q": " A ", "q2": "A"}, "saved_detail_versions": {"institution": 0}}
    assert validate_submission(schema=form, payload=payload).profile_values == {"institution": "A"}
    payload["answers"]["q2"] = "B"
    with pytest.raises(ValidationError, match="duplicate_profile_mapping"):
        validate_submission(schema=form, payload=payload)


def test_receiving_choices_never_translate_foreign_labels_or_hidden_values():
    form = schema(question("single_choice", profile_field_key="shirt_size", options=[{"id": "medium", "label": "M"},
        {"id": "other", "label": "Other"}]),
        question(id="notes", profile_field_key="institution", show_if={"all": [{"field_id": "q", "op": "eq", "value": "other"}]}))
    values, defaults = prefill_for_schema(form, {"shirt_size": "M", "institution": "Hidden"})
    assert values == {} and defaults == {"shirt_size": True}
    values, _ = prefill_for_schema(form, {"shirt_size": "medium"})
    assert values == {"q": {"option_id": "medium"}}


def test_server_metadata_never_accepts_a_client_answer_or_save_choice():
    form = schema(question(visibility="server", required=True))
    result = validate_submission(schema=form, payload={"answers": {"q": "privileged"}})
    assert result.snapshot["answers"] == [] and result.omitted_question_ids == ("q",)


def test_profile_normalization_is_contact_only_and_closed():
    assert normalize_profile_value("phone", "00 91 (98765) 43210") == "+919876543210"
    assert normalize_profile_value("country", "in") == "IN"
    assert normalize_profile_value("skills", [" CAD ", "CAD", "Python"]) == ["CAD", "Python"]
    for key, value in (("country", "ZZ"), ("resume", {"asset_id": 1, "url": "https://x.test"}), ("unknown", "x")):
        with pytest.raises(ValueError):
            normalize_profile_value(key, value)


def test_impossible_choice_minimum_and_enormous_number_bound_are_schema_errors():
    from django.core.exceptions import ValidationError as SchemaError
    from apps.forms_schema.validation import validate_form_schema
    for form in (schema(question("multi_choice", options=[{"id": "a", "label": "A"}], bounds={"min_selections": 2})),
                 schema(question("number", bounds={"min": 10 ** 1000}))):
        with pytest.raises(SchemaError):
            validate_form_schema(form)


def test_condition_operands_preserve_boolean_number_types_and_normalized_text():
    from django.core.exceptions import ValidationError as SchemaError
    from apps.forms_schema.validation import validate_form_schema
    form = schema(question("yes_no"), question(id="child", show_if={"all": [{"field_id": "q", "op": "eq", "value": 1}]}))
    with pytest.raises(SchemaError):
        validate_form_schema(form)
    form = schema(question(), question(id="child", required=True, show_if={"all": [{"field_id": "q", "op": "eq", "value": "yes"}]}))
    with pytest.raises(ValidationError) as caught:
        validate_answers(form, {"q": " yes "})
    assert "child" in caught.value.detail["fields"]


def test_expanded_literal_other_contract():
    import json
    from pathlib import Path
    data = json.loads((Path(__file__).parent / "fixtures" / "f-expanded-form-v3.json").read_text(encoding="utf-8"))
    item = data["single_choice_other"]
    assert validate_answers(item["schema"], item["raw"])["answers"][0]["value"] == item["canonical_value"]
