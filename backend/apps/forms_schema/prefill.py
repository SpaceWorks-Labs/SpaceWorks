"""Receiving-schema validation for an owner's reviewable draft; no vault access."""
from .answers_v2 import normalize_answer
from .conditions import visible
from .profile_fields import PROFILE_FIELDS, ProfileValueError, normalize_profile_value
from .schema_v2 import validate_schema


def prefill_for_schema(schema, saved_values, *, context=None):
    """Only P may supply owner-decrypted values after loading the real event schema.

    Returns raw question-ID answers and per-key save defaults, never derived age.
    Option labels from a different form are deliberately not translated into IDs.
    """
    schema = validate_schema(schema, context=context)
    answers, defaults = {}, {}
    for question in schema["questions"]:
        key, qid = question.get("profile_field_key"), question["id"]
        if (not key or question.get("visibility") == "server"
                or not visible(question.get("show_if"), answers)):
            continue
        defaults[key] = PROFILE_FIELDS[key].default_save and not question.get("sensitive", False)
        if key not in saved_values or not PROFILE_FIELDS[key].persistable:
            continue
        try:
            value = normalize_profile_value(key, saved_values[key])
            if question["type"] == "single_choice":
                value = {"option_id": value}
            elif question["type"] == "multi_choice":
                value = {"option_ids": value}
            value = normalize_answer(question, value)
        except ProfileValueError:
            continue
        if value is not None:
            answers[qid] = value
    return answers, defaults
