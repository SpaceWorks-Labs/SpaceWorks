"""L21a stage-aware reimbursement eligibility and crew claims behind events.crew_claims."""
from types import SimpleNamespace

import pytest

from apps.event_reimbursements import eligibility
from apps.payments.event_payouts.errors import PayoutError

pytestmark = pytest.mark.django_db
VALUE = {"estimates": [{"category": "rail", "currency": "INR", "amount_minor": 100}]}


def programme(min_stage=None, features=()):
    space = SimpleNamespace(enabled_features=list(features))
    return SimpleNamespace(min_application_stage=min_stage, eligible_countries=[], eligible_cohorts=[],
                           min_distance_km=None, allowed_categories=["rail"], exclusions=[], currency="INR",
                           event=SimpleNamespace(makerspace=space))


def test_request_needs_the_application_to_stand_in_stage_n():
    with pytest.raises(PayoutError) as exc:
        eligibility.validate_request(programme(2), VALUE, {"application_stage": 1})
    assert "application_stage_required" in str(exc.value.detail)
    eligibility.validate_request(programme(2), VALUE, {"application_stage": 2})
    eligibility.validate_request(programme(None), VALUE, {})


def test_crew_claims_need_their_own_switch(monkeypatch):
    monkeypatch.setattr("apps.makerspaces.platform.feature_enabled", lambda space, key: key in space.enabled_features)
    with pytest.raises(PayoutError) as exc:
        eligibility.validate_request(programme(3), VALUE, {"crew": True})
    assert "crew_claims_disabled" in str(exc.value.detail)
    eligibility.validate_request(programme(3, ["events.crew_claims"]), VALUE, {"crew": True})
