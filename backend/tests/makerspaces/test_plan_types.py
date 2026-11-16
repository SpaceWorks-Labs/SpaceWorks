"""G16/X6: plan types, renewal prices, per-plan fees and rejoin rules, late renewals, the switch."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.makerspaces.financial_year import fy_end_at
from apps.makerspaces.membership_admission_settings import settings_for
from apps.makerspaces.membership_plan_policy import joining_fee_for
from apps.makerspaces.membership_plan_services import create_term
from apps.makerspaces.membership_plan_types import late_renewal_start, term_end
from apps.makerspaces.models import MembershipTerm
from apps.makerspaces.models_membership_rules import PlanType
from apps.makerspaces.models_membership_terms import LIFETIME_ENDS_AT
from tests.makerspaces.l4_helpers import features_off, features_on, member, plan, space_with_manager
from tests.return_helpers import authenticated_client, make_space

pytestmark = pytest.mark.django_db


def test_financial_year_plan_ends_at_the_fy_end():
    space = make_space("pt-fy")
    fy = plan(space, plan_type=PlanType.FINANCIAL_YEAR)
    start = timezone.now()
    assert term_end(fy, start) == fy_end_at(space, start)


def test_fixed_end_and_lifetime_plans():
    space = make_space("pt-fixed")
    fixed = plan(space, "Season", plan_type=PlanType.FIXED_END, fixed_end_date=date(2099, 6, 30))
    assert term_end(fixed, timezone.now()).date() >= date(2099, 6, 30)
    life = plan(space, "Life", plan_type=PlanType.LIFETIME)
    assert term_end(life, timezone.now()) == LIFETIME_ENDS_AT
    assert not life.renews and fixed.renews is False


def test_term_freezes_price_and_uses_renewal_price_for_renewals():
    space, manager = space_with_manager("pt-price")
    yearly = plan(space, "Yearly", "yearly", amount="100.00", renewal_amount=Decimal("80.00"))
    membership = member("pt-price", space)
    first = create_term(manager, membership, yearly)
    second = create_term(manager, membership, yearly)
    assert (first.kind, first.price, first.currency) == ("new", Decimal("100.00"), "usd")
    assert (second.kind, second.price) == ("renewal", Decimal("80.00"))
    yearly.amount = Decimal("150.00")
    yearly.save()
    first.refresh_from_db()
    assert first.price == Decimal("100.00")  # a later price edit never rewrites what was sold


def test_lifetime_member_cannot_hold_a_second_term():
    space, manager = space_with_manager("pt-life")
    life = plan(space, "Life", plan_type=PlanType.LIFETIME)
    membership = member("pt-life", space)
    term = create_term(manager, membership, life)
    assert term.is_lifetime
    with pytest.raises(Exception):
        create_term(manager, membership, life)


def test_fixed_date_in_the_past_is_refused():
    space, manager = space_with_manager("pt-past")
    over = plan(space, "Over", plan_type=PlanType.FIXED_END, fixed_end_date=date(2000, 1, 1))
    with pytest.raises(Exception):
        create_term(manager, member("pt-past", space), over)


def test_per_plan_joining_fee_and_rejoin_rules():
    space = make_space("pt-fee")
    policy = settings_for(space)
    policy.joining_fee = Decimal("50.00")
    user = member("pt-fee", space).user
    free = plan(space, "Free join", joining_fee=Decimal("0.00"))
    assert joining_fee_for(space, policy, free, user, rejoining=False)[0] == Decimal("0.00")
    special = plan(space, "Special", joining_fee=Decimal("20.00"), rejoin_rule="each_join")
    assert joining_fee_for(space, policy, special, user, rejoining=True)[0] == Decimal("20.00")
    never = plan(space, "Never", rejoin_rule="never")
    assert joining_fee_for(space, policy, never, user, rejoining=False)[0] == Decimal("0.00")
    once = plan(space, "Once")
    assert joining_fee_for(space, policy, once, user, rejoining=True)[0] == Decimal("0.00")


def test_after_lapse_rule_charges_only_after_enough_days_away():
    space, manager = space_with_manager("pt-lapse")
    membership = member("pt-lapse", space)
    monthly = plan(space, joining_fee=Decimal("30.00"), rejoin_rule="after_lapse", rejoin_after_days=90)
    term = create_term(manager, membership, monthly)
    policy = settings_for(space)
    now = term.ends_at + timedelta(days=10)
    assert joining_fee_for(space, policy, monthly, membership.user, rejoining=True, now=now)[0] == Decimal("0.00")
    later = term.ends_at + timedelta(days=200)
    assert joining_fee_for(space, policy, monthly, membership.user, rejoining=True, now=later)[0] == Decimal("30.00")


def test_late_renewal_backdates_or_starts_on_payment_day():
    space, manager = space_with_manager("pt-late")
    backdate = plan(space, "Back", "yearly")
    payday = plan(space, "Pay", "yearly", late_renewal="payment_day")
    term = create_term(manager, member("pt-late", space), backdate)
    now = term.ends_at + timedelta(days=5)
    assert late_renewal_start(backdate, term, now) == term.ends_at
    assert late_renewal_start(payday, term, now) == now


def test_plan_rules_need_their_switch_on_the_plan_api():
    space, manager = space_with_manager("pt-switch")
    client = authenticated_client(manager)
    url = reverse("admin-membership-plans", args=[space.pk])
    body = {"name": "FY", "interval": "yearly", "amount": "10.00", "currency": "usd", "plan_type": "financial_year"}
    features_off(space)
    refused = client.post(url, body, format="json")
    assert refused.status_code == 403 and refused.json()["code"] == "feature_disabled"
    features_on(space, "plan_rules")
    created = client.post(url, body, format="json")
    assert created.status_code == 201, created.content
    assert created.json()["plan_type"] == "financial_year"
    # Switching off keeps the data and lets the same values be posted back unchanged.
    features_off(space, "plan_rules")
    detail = reverse("admin-membership-plan-detail", args=[created.json()["id"]])
    assert client.patch(detail, {"name": "FY renamed", "plan_type": "financial_year"}, format="json").status_code == 200
    assert MembershipTerm.objects.count() == 0


def test_public_listing_fields_need_public_plans():
    space, manager = space_with_manager("pt-public")
    client = authenticated_client(manager)
    url = reverse("admin-membership-plans", args=[space.pk])
    body = {"name": "Card", "interval": "monthly", "amount": "5.00", "currency": "usd", "is_public": True, "slug": "card"}
    assert client.post(url, body, format="json").status_code == 403
    features_on(space, "public_plans")
    assert client.post(url, body, format="json").status_code == 201
