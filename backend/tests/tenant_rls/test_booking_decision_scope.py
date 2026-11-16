"""Source-level owner and generated policy declaration for the venue decision."""
import pytest
from apps.tenant_rls.scope_registry import predicates
from apps.tenant_rls.policies import build_plans


@pytest.mark.django_db
def test_venue_decision_has_maker_and_parent_scoped_policy():
    scope = predicates()["events.EventBookingDecision"]
    assert scope.any_paths == ("makerspace",)
    assert not scope.includes({"makerspace": 2}, 1)
    plans, unresolvable = build_plans()
    assert "events.EventBookingDecision" in plans
    assert "events.EventBookingDecision" not in unresolvable
