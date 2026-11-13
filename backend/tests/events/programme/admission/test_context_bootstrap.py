"""Token bootstrap producer consumes the exact G joint fixture."""
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import pytest
from apps.events.hackathons import api_context
from apps.events.hackathons.admission_errors import ProgrammeError

FIXTURES = Path(__file__).parents[1] / "contracts" / "fixtures"


class Query:
    def __init__(self, value):
        self.value = value
    def filter(self, **kwargs):
        return self
    def first(self):
        return self.value


def setup(monkeypatch):
    fixture = json.loads((FIXTURES / "public-url-bootstrap-v4.json").read_text())
    current = fixture["context"]
    event = SimpleNamespace(pk=42, makerspace_id=9, makerspace=SimpleNamespace(slug="workshop"),
        public_token=current["event"]["public_token"], event_date_revision=7,
        starts_at=datetime.fromisoformat(current["event"]["starts_at"].replace("Z", "+00:00")),
        ends_at=datetime.fromisoformat(current["event"]["ends_at"].replace("Z", "+00:00")),
        timezone_name="Asia/Kolkata", registrations=Query(None), custom_form=[])
    config = SimpleNamespace(application_form={k: v for k, v in current["application_form"].items() if k != "event_context"},
        coc_revision=5, team_mode="individual_then_team", finder_enabled=True)
    actor = SimpleNamespace(pk=18, account_kind="member", retired_at=None, is_authenticated=True, is_active=True,
                            access_status="active", email="", phone="")
    monkeypatch.setattr(api_context, "resolve", lambda slug, token: event)
    monkeypatch.setattr(api_context.HackathonConfig.objects, "filter", lambda **kwargs: Query(config))
    monkeypatch.setattr(api_context, "require_registration_access", lambda *args: None)
    monkeypatch.setattr(api_context, "get_object_or_404", lambda *args, **kwargs: SimpleNamespace(revision=5, body="Fixture CoC."))
    monkeypatch.setattr(api_context, "feature_enabled", lambda space, key: current["programme"]["capabilities"][key])
    monkeypatch.setattr(api_context, "admission_requirements", lambda *args, **kwargs: current["admission_requirements"])
    monkeypatch.setattr(api_context, "ports", lambda: SimpleNamespace(context_gate=lambda **kwargs: None, readiness=lambda **kwargs: "ready"))
    return fixture, event, config, actor


def test_member18_needs_no_membership_application_profile_or_saved_rows(monkeypatch):
    fixture, event, config, actor = setup(monkeypatch)
    result = api_context.context_for_token(public_token=event.public_token, actor=actor)
    normalized = json.loads(json.dumps(result, default=lambda value: value.isoformat().replace("+00:00", "Z")))
    assert normalized == fixture["context"]
    assert fixture["setup"]["memberships"] == []


def test_enabled_config_with_disabled_feature_never_falls_back_to_ordinary(monkeypatch):
    fixture, event, config, actor = setup(monkeypatch)
    monkeypatch.setattr(api_context, "feature_enabled", lambda *args: False)
    with pytest.raises(ProgrammeError) as exc:
        api_context.context_for_token(public_token=event.public_token, actor=actor)
    assert exc.value.status_code == 404


def test_no_config_advertises_only_existing_ordinary_registration(monkeypatch):
    fixture, event, config, actor = setup(monkeypatch)
    monkeypatch.setattr(api_context.HackathonConfig.objects, "filter", lambda **kwargs: Query(None))
    result = api_context.context_for_token(public_token=event.public_token, actor=actor)
    assert result["programme"]["kind"] == "ordinary" and result["application_form"] is None
    assert result["routes"]["application"] is None
    assert result["routes"]["ordinary_register"]["name"] == "public-event-register"


def test_ineligible_account_gets_requirements_but_no_admission_or_prefill_routes(monkeypatch):
    from rest_framework.exceptions import PermissionDenied
    fixture, event, config, actor = setup(monkeypatch)
    monkeypatch.setattr(api_context, "require_registration_access", lambda *args: (_ for _ in ()).throw(PermissionDenied()))
    result = api_context.context_for_token(public_token=event.public_token, actor=actor)
    assert result["eligibility"]["eligible"] is False
    assert all(value is None for key, value in result["routes"].items() if key not in ("context", "member_base"))


def test_generic_applications_producer_matches_the_documented_programme_choice(monkeypatch):
    from apps.events.hackathons.api_schema_details import ContextProgrammeSerializer

    fixture, event, config, actor = setup(monkeypatch)
    config.team_mode, config.finder_enabled = "solo", False
    monkeypatch.setattr(api_context, "feature_enabled", lambda space, key: key == "events.applications")
    result = api_context.context_for_token(public_token=event.public_token, actor=actor)
    assert result["programme"]["kind"] == "applications"
    assert result["programme"]["capabilities"]["events.hackathons"] is False
    assert result["routes"]["application_submit"] is not None
    assert fixture["setup"]["memberships"] == []
    documented = ContextProgrammeSerializer(data=result["programme"])
    assert documented.is_valid(), documented.errors
    assert documented.validated_data["kind"] == "applications"
    unknown = ContextProgrammeSerializer(data={**result["programme"], "kind": "future-programme"})
    assert not unknown.is_valid() and unknown.errors["kind"][0].code == "invalid_choice"
