"""Every generated immutable core summary must satisfy G1's frozen closed schema."""
import json
from pathlib import Path
import pytest
from apps.event_reimbursements import claim_workflow
from apps.event_reimbursements.decision_summary import utc
from apps.payments.event_payouts.obligation_models import EventPayoutObligation
from tests.events.programme.test_reimbursement_contract_fixtures import validate_fixture
from .helpers import submitted, decision_data

CONTRACT = json.loads((Path(__file__).resolve().parents[1] / "events/programme/contracts/reimbursement_addon.json").read_text())


def test_generated_fixed_request_schema_matches_frozen_g1_exactly():
    from types import SimpleNamespace
    from apps.event_reimbursements.request_form_adapter import schema
    programme = SimpleNamespace(pk=9, version=3, currency="INR", allowed_categories=["rail", "lodging"])
    assert schema(programme) == CONTRACT["submission"]["fixed_request_schema"]


@pytest.mark.django_db(transaction=True)
def test_real_decision_summary_matches_frozen_g1_closed_schema(world, monkeypatch):
    claim, asset, line_id = submitted(world, monkeypatch)
    claim_workflow.decide(request=world.finance, event_id=world.event.pk, claim_id=claim.pk,
        data=decision_data(world, claim, line_id, 9000, outcome="partially_approved"))
    obligation = EventPayoutObligation.objects.get(source_uuid=claim.uuid)
    value = json.loads(obligation.current_revision.decision_summary)
    validate_fixture(CONTRACT["schemas"]["decision_summary"], value)
    assert sum(row["approved_minor"] for row in value["lines"]) == value["totals"]["approved_minor"]
    assert value["lines"][0]["receipt"]["generation"] == asset.generation
    assert value["eligibility"]["core_eligibility_revision"] == obligation.eligibility_revision


def test_utc_identity_matches_frozen_seconds_and_fraction_policy():
    from datetime import datetime
    value = CONTRACT["rsvp_identity"]["instant"]
    assert utc(datetime.fromisoformat(value.replace("Z", "+00:00"))) == value
    assert utc(datetime.fromisoformat("2026-12-01T15:30:00+05:30")) == value
    assert utc(datetime.fromisoformat("2026-12-01T10:00:00.123456+00:00")) == "2026-12-01T10:00:00.123456Z"
