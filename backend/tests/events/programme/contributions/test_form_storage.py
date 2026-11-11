import json
import pytest
from apps.events.contributions.form_storage import canonical_answers
from apps.events.contributions.errors import ProgrammeError


def test_age_slot_stores_derivation_reference_not_numeric_age_or_dob():
    answer = {"id": "age", "label": "Age at event", "type": "age_at_event", "derivation_id": 19}
    assert json.loads(canonical_answers(json.dumps({"version": 2, "answers": [answer]})))["answers"] == [answer]
    for extra in ({"value": 18}, {"date_of_birth": "2008-01-01"}, {"as_of_date": "2026-12-01"}):
        with pytest.raises(ProgrammeError):
            canonical_answers(json.dumps({"version": 2, "answers": [{**answer, **extra}]}))


def test_explicit_dob_question_is_an_independently_encrypted_submitted_answer():
    document = {"version": 2, "answers": [{"id": "dob", "type": "date_of_birth", "value": "2000-02-29"}]}
    assert json.loads(canonical_answers(json.dumps(document))) == document
