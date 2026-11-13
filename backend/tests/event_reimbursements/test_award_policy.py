"""Every award mode is bounded by its current finance-approved rule."""
import pytest
from apps.event_reimbursements import programme_workflow, award_workflow
from apps.event_reimbursements.models import GrantAward
from apps.payments.event_payouts.errors import PayoutError
from .conftest import cmd
from .helpers import requested

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("mode,rules,bad,good,tier", [
    ("need_based", {"cap_minor": 5000}, 5001, 5000, None),
    ("fixed_tier", {"standard": {"amount_minor": 6000}}, 5999, 6000, "standard"),
    ("percentage", {"basis_points": 5000, "cap_minor": 4000}, 4001, 4000, None),
    ("route_cap", {"rail": {"priority": 1, "mode": "rail", "amount_minor": 3000}}, 3001, 3000, "rail"),
])
def test_award_modes_apply_caps_and_rollback_rejected_offer(world, mode, rules, bad, good, tier):
    world.programme.refresh_from_db(); world.pool.refresh_from_db()
    programme_workflow.configure(request=world.finance, event_id=world.event.pk,
        data=cmd(world.programme.version, policy_revision=world.programme.finance_policy_revision,
            settings={"award_mode": mode, "tier_rules": rules}, pool_id=world.pool.pk,
            expected_pool_version=world.pool.version, budget_delta_minor=0, reason_code="approved"))
    world.programme.refresh_from_db(); world.pool.refresh_from_db()
    grant = requested(world)
    value = cmd(grant.version, outcome="award", amount_minor=bad, currency="INR", reason_code="need_based",
        expected_award_version=None, expected_pool_version=world.pool.version)
    if tier:
        value["tier"] = tier
    with pytest.raises(PayoutError):
        award_workflow.decide(request=world.finance, event_id=world.event.pk, request_id=grant.pk, data=value)
    world.pool.refresh_from_db()
    assert world.pool.reserved_minor == 0 and not GrantAward.objects.filter(request=grant).exists()
    value = {**value, "operation_id": cmd()["operation_id"], "amount_minor": good}
    award_workflow.decide(request=world.finance, event_id=world.event.pk, request_id=grant.pk, data=value)
    world.pool.refresh_from_db()
    assert world.pool.reserved_minor == good


def test_route_priority_is_deterministic_and_reviewer_cannot_select_more_generous_match(world):
    programme_workflow.configure(request=world.finance, event_id=world.event.pk,
        data=cmd(world.programme.version, policy_revision=world.programme.finance_policy_revision,
            settings={"award_mode": "route_cap", "tier_rules": {"near": {"priority": 1, "mode": "rail", "amount_minor": 3000},
                "fallback": {"priority": 2, "amount_minor": 9000}}}, pool_id=world.pool.pk,
            expected_pool_version=world.pool.version, budget_delta_minor=0, reason_code="approved"))
    world.programme.refresh_from_db(); world.pool.refresh_from_db()
    grant = requested(world)
    with pytest.raises(PayoutError) as exc:
        award_workflow.decide(request=world.finance, event_id=world.event.pk, request_id=grant.pk,
            data=cmd(grant.version, outcome="award", amount_minor=9000, currency="INR", tier="fallback", reason_code="tier_award",
                expected_award_version=None, expected_pool_version=world.pool.version))
    assert exc.value.detail["code"] == "route_tier_mismatch"
