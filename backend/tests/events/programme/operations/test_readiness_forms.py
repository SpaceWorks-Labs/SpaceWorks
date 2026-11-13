import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from rest_framework.exceptions import ValidationError

from apps.events.programme import forms, readiness
from apps.events.programme.providers import ReadinessProvider
from apps.events.programme.serializers import FormValidationInput, PublishingInput
from apps.events.programme.commands import ProgrammeConflict


FIXTURES = Path(__file__).parents[1] / "contracts" / "fixtures"


def test_readiness_does_not_query_inaccessible_counts_or_providers(monkeypatch):
    event = SimpleNamespace(pk=42, version=4, status="published", makerspace=object(), registrations=Mock())
    summarize = Mock()
    monkeypatch.setattr(readiness.event_authority, "require", Mock())
    monkeypatch.setattr(readiness.event_authority, "can", lambda *args: False)
    monkeypatch.setattr(readiness, "readiness_providers", lambda: (
        ReadinessProvider("help", "mentor_queue", "Help", "mentoring", "events.mentoring", summarize),))
    data = readiness.project_readiness(event, actor=object())
    assert data["items"] == []
    event.registrations.filter.assert_not_called()
    summarize.assert_not_called()


def test_provider_counts_are_not_duplicated_by_ops(monkeypatch):
    event = SimpleNamespace(pk=42, version=4, status="published", makerspace=object(), registrations=Mock())
    monkeypatch.setattr(readiness.event_authority, "require", Mock())
    monkeypatch.setattr(readiness.event_authority, "can", lambda actor, event, permission: permission == "mentor_queue")
    monkeypatch.setattr(readiness, "feature_enabled", lambda *args: True)
    summarize = Mock(return_value={"status": "action", "count": 3})
    monkeypatch.setattr(readiness, "readiness_providers", lambda: (
        ReadinessProvider("help", "mentor_queue", "Teams waiting for help", "mentoring", "events.mentoring", summarize),))
    data = readiness.project_readiness(event, actor=object())
    assert next(row for row in data["items"] if row["code"] == "help")["count"] == 3
    summarize.assert_called_once()


def test_frozen_form_preview_accepts_partial_answers_without_requiring_private_dob(monkeypatch):
    monkeypatch.setattr(forms.event_authority, "require", Mock())
    data = json.loads((FIXTURES / "routes-v3.json").read_text(encoding="utf-8"))
    route = next(route for route in data["routes"] if route["name"] == "events-programme-admin-form-validate")
    request = route["operations"]["POST"]["request_example"]
    parsed = FormValidationInput(data=request)
    assert parsed.is_valid(), parsed.errors
    response = forms.validate_form_preview(object(), actor=object(), key="registration", **parsed.validated_data)
    assert response == route["operations"]["POST"]["response_example"]


def test_preview_invalid_sample_returns_nested_errors_without_persistence(monkeypatch):
    monkeypatch.setattr(forms.event_authority, "require", Mock())
    schema = {"schema_version": 2, "form_id": "example", "revision": 1, "questions": [
        {"id": "email", "label": "Email", "type": "email", "required": True}]}
    result = forms.validate_form_preview(object(), actor=object(), key="registration", schema=schema,
                                         sample_answers={"email": "invalid"})
    assert result["valid"] is False
    assert "email" in result["errors"]


def test_publishing_rejects_unknown_fields_and_release_without_saved_revision():
    payload = {"operation_id": "11111111-1111-4111-8111-111111111111", "expected_version": 4,
               "release_saved_website": True}
    serializer = PublishingInput(data=payload)
    assert not serializer.is_valid()
    assert "website_revision" in serializer.errors
    serializer = PublishingInput(data={**payload, "website_revision": 5, "arbitrary_color": "#abc"})
    assert not serializer.is_valid()
    assert "arbitrary_color" in serializer.errors


def test_editor_revision_is_compared_even_with_current_aggregate_version():
    with pytest.raises(ProgrammeConflict) as error:
        forms.check_editor_revision({"schema_version": 2, "revision": 2}, {"revision": 3})
    assert error.value.detail["code"] == "form_revision_changed"
    forms.check_editor_revision({"schema_version": 2, "revision": 3}, {"revision": 3})


def test_editor_cannot_save_server_event_context(monkeypatch):
    monkeypatch.setattr(forms, "require_form", Mock())
    execute = Mock()
    monkeypatch.setattr(forms, "execute_command", execute)
    with pytest.raises(ValidationError) as error:
        forms.save_form(object(), actor=object(), key="registration", data={"schema": {
            "schema_version": 2, "event_context": {"event_id": 99}}})
    assert error.value.detail["code"] == "invalid_form_schema"
    execute.assert_not_called()
