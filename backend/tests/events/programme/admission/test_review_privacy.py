import pytest
from apps.events.hackathons.review_projection import reviewer_answers, alias
from apps.events.hackathons.review_workflow import validate_scores
from apps.events.hackathons.serializers_config import validate_rubric
from apps.events.hackathons.admission_errors import ProgrammeError
from rest_framework.exceptions import ValidationError


def test_blind_allowlist_removes_identifying_and_undisclosed_answers():
    questions = [
        {"id": "work", "type": "long_text", "disclosure": {"reviewer": True}},
        {"id": "school", "type": "short_text", "profile_field_key": "institution", "disclosure": {"reviewer": True}},
        {"id": "emergency", "type": "emergency_contact", "disclosure": {"reviewer": True}},
        {"id": "secret", "type": "short_text", "disclosure": {"reviewer": False}},
        {"id": "age", "type": "age_at_event", "disclosure": {"reviewer": True}},
    ]
    entries = [{"id": q["id"], "label": q["id"], "type": q["type"], "value": "private"} for q in questions]
    entries[-1] = {"id": "age", "type": "age_at_event", "derivation_id": 1}
    result = reviewer_answers({"version": 2, "answers": entries}, {"questions": questions}, blind=True)
    assert [r["id"] for r in result] == ["work"]
    assert "private" not in str(reviewer_answers({"version": 1}, [], blind=True))


def test_alias_is_event_local_and_contains_no_member_identity(settings):
    settings.SECRET_KEY = "fixture-key"
    assert alias(42, 61) == alias(42, 61)
    assert alias(43, 61) != alias(42, 61)


def rubric():
    return {"revision": 1, "criteria": [{"key": "craft", "label": "Craft", "anchors": {str(n): f"Level {n}" for n in range(1, 6)}}]}


@pytest.mark.parametrize("scores", [{}, {"craft": 6}, {"craft": True}, {"craft": 3, "extra": 2}])
def test_scores_need_every_anchored_criterion_and_literal_integer(scores):
    with pytest.raises(ProgrammeError):
        validate_scores(rubric(), scores)


def test_rubric_requires_all_five_anchors():
    value = rubric()
    assert validate_rubric(value) == value
    value["criteria"][0]["anchors"].pop("5")
    with pytest.raises(ValidationError):
        validate_rubric(value)
