"""Approved, age-free MLH data-sharing application presets (EP-9, decision 9).

A hackathon that shares applicant data with Major League Hacking asks the extra questions MLH needs as an
OPTIONAL form: each applicant separately opts in, and consent starts off (`admission_workflow`). Staff pick one
of these presets in the admission settings and the chosen schema is stored on the programme's
`optional_mlh_schema`. They are static per deployment, closed form-v2 schemas, and deliberately carry no age,
date-of-birth or guardian question (age gating is forbidden in programme forms).
"""
from copy import deepcopy

from .schema_v2 import validate_schema


def _q(qid, kind, label, *, required=False, help_text="", options=None, bounds=None):
    row = {"id": qid, "type": kind, "label": label, "required": required}
    if help_text:
        row["help"] = help_text
    if options:
        row["options"] = [{"id": key, "label": text} for key, text in options]
    if bounds:
        row["bounds"] = bounds
    return row


_STUDY = (("secondary", "Secondary / high school"), ("undergraduate", "Undergraduate"),
          ("graduate", "Graduate"), ("bootcamp", "Bootcamp or self-taught"), ("other", "Other"))
_SHIRT = (("xs", "XS"), ("s", "S"), ("m", "M"), ("l", "L"), ("xl", "XL"), ("xxl", "XXL"))

_PRESETS = (
    {"id": "mlh-2026", "label": "MLH data sharing (standard)", "schema": {
        "schema_version": 2, "form_id": "mlh-application", "revision": 1, "questions": [
            _q("mlh_school", "short_text", "School or institution", required=True, bounds={"max_length": 200}),
            _q("mlh_level_of_study", "single_choice", "Level of study", required=True, options=_STUDY),
            _q("mlh_major", "short_text", "Major or field of study", bounds={"max_length": 200}),
            _q("mlh_graduation_year", "number", "Expected graduation year", bounds={"min": 1950, "max": 2100}),
            _q("mlh_country", "short_text", "Country of residence", required=True, bounds={"max_length": 100}),
            _q("mlh_phone", "phone", "Phone number", help_text="MLH may use this for event safety messages."),
            _q("mlh_shirt_size", "single_choice", "T-shirt size", options=_SHIRT),
        ]}},
    {"id": "mlh-basics", "label": "MLH data sharing (basics only)", "schema": {
        "schema_version": 2, "form_id": "mlh-application-basics", "revision": 1, "questions": [
            _q("mlh_school", "short_text", "School or institution", required=True, bounds={"max_length": 200}),
            _q("mlh_level_of_study", "single_choice", "Level of study", required=True, options=_STUDY),
            _q("mlh_country", "short_text", "Country of residence", required=True, bounds={"max_length": 100}),
        ]}},
)


def mlh_presets():
    """Deep copies of the presets, each schema validated against the closed form-v2 vocabulary."""
    result = []
    for preset in _PRESETS:
        schema = validate_schema(deepcopy(preset["schema"]))
        result.append({"id": preset["id"], "label": preset["label"], "schema": schema})
    return result
