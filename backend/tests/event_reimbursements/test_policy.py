"""Boundary policies reject ambiguous money, unsupported rules and private fields."""
from datetime import timedelta
from types import SimpleNamespace
import pytest
from django.utils import timezone
from apps.event_reimbursements.policy import validate_policy
from apps.event_reimbursements.serializers_finance import ClaimReviewCommand, ProgrammeCreateOrGetCommand
from apps.event_reimbursements.serializers_request import ReimbursementRequestSubmissionSerializer
from apps.event_reimbursements.request_form_adapter import prepare
from apps.payments.event_payouts.errors import PayoutError
from .helpers import block
from .conftest import cmd


@pytest.mark.parametrize("policy_settings", [
    {"tax_required": True}, {"eligible_countries": ["in"]}, {"min_distance_km": "NaN"},
    {"award_accept_days": True}, {"allowed_categories": ["rail", "rail"]},
    {"permitted_venue_sources": ["online"]}, {"category_limits": {"visa": 100}},
    {"award_mode": "percentage", "tier_rules": {"basis_points": 10001, "cap_minor": 100}},
    {"award_mode": "route_cap", "tier_rules": {"near": {"amount_minor": 100, "priority": 1},
        "far": {"amount_minor": 200, "priority": 1}}},
])
def test_policy_refuses_invalid_rules(policy_settings):
    event = SimpleNamespace(ends_at=timezone.now())
    with pytest.raises((PayoutError, ValueError)):
        validate_policy(policy_settings, event=event)


def test_claim_review_has_no_implicit_finance_default():
    serializer = ClaimReviewCommand(data=cmd(1, outcome="approved"))
    assert not serializer.is_valid()
    assert str(serializer.errors["code"]) == "review_mode_required"


@pytest.mark.django_db(transaction=True)
def test_request_consent_unknown_bank_and_stale_programme(world):
    original = block(world)
    for changes in ({"submit": "true"}, {"submit": False}, {"bank_account": "secret"}, {"owner": world.owner.pk}):
        serializer = ReimbursementRequestSubmissionSerializer(data={**original, **changes})
        assert not serializer.is_valid()
        assert "secret" not in str(serializer.errors)
    changed = {**original, "programme_version": world.programme.version - 1}
    with pytest.raises(PayoutError) as exc:
        prepare(programme=world.programme, event=world.event, actor=world.owner,
            operation_id=cmd()["operation_id"], block=changed)
    assert exc.value.detail["code"] == "programme_version_changed"


@pytest.mark.django_db(transaction=True)
def test_request_minimum_distance_and_country_policy_are_rechecked(world):
    from .helpers import participate
    participate(world)
    world.programme.min_distance_km = 600
    value = block(world)
    with pytest.raises(PayoutError):
        prepare(programme=world.programme, event=world.event, actor=world.owner, operation_id=cmd()["operation_id"], block=value)
    world.programme.min_distance_km = None
    world.programme.eligible_countries = ["IN"]
    with pytest.raises(PayoutError) as exc:
        prepare(programme=world.programme, event=world.event, actor=world.owner, operation_id=cmd()["operation_id"], block=value)
    assert exc.value.detail["code"] == "country_ineligible"
