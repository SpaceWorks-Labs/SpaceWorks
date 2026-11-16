"""Lane L15 (A3/A4): one best automatic discount, exclusions, audiences, window."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.payments.models import PriceDiscount
from apps.payments.pricing import quote
from tests.payments.pricing.helpers import D, member, plan, pricing_space, put_on_plan, rate, switch
from tests.return_helpers import make_product

pytestmark = pytest.mark.django_db


def rule(space, creator, audience="all_members", **fields):
    return PriceDiscount.objects.create(makerspace=space, name=fields.pop("name", "Rule"), audience=audience,
                                        created_by=creator, **fields)


def loan_quote(space, who, product, components=("rental",)):
    return quote(space, "loans", member=who, params={"items": [(product, 1)], "days": 2, "components": components})


@pytest.fixture
def space_setup():
    space, manager = pricing_space("disc", "charges.discounts")
    product = make_product(space)
    rate(space, "loans", rental_per_day="10.00")
    return space, manager, product


def test_best_single_rule_wins_and_nothing_stacks(space_setup):
    space, manager, product = space_setup
    pro = plan(space)
    buyer = member(space)
    put_on_plan(space, buyer, pro)
    rule(space, manager, percent_bps=1000, name="Everyone 10%")
    best = rule(space, manager, audience="plan", plan=pro, percent_bps=2500, name="Pro 25%")
    rule(space, manager, audience="member", member=buyer, amount_off=D("3.00"), name="Three off")
    priced = loan_quote(space, buyer, product)
    assert priced.discount["id"] == best.pk and priced.total == D("15.00")


def test_non_members_and_other_plans_get_no_member_price(space_setup):
    space, manager, product = space_setup
    pro, basic = plan(space, "Pro"), plan(space, "Basic")
    rule(space, manager, audience="plan", plan=pro, percent_bps=5000)
    basic_member = member(space)
    put_on_plan(space, basic_member, basic)
    from tests.return_helpers import make_user
    outsider = make_user("disc-outsider")
    assert loan_quote(space, basic_member, product).discount is None
    assert loan_quote(space, outsider, product).discount is None


def test_deposits_late_damage_lost_are_never_discounted_unless_named():
    space, manager = pricing_space("disc-excl", "charges.discounts", loan_deposit_mode="fixed",
                                   loan_deposit_amount=D("20.00"))
    product = make_product(space)
    buyer = member(space)
    rule(space, manager, percent_bps=5000)
    assert loan_quote(space, buyer, product, ("deposit",)).total == D("20.00")
    rule(space, manager, percent_bps=1000, components=["deposit"], name="Deposit 10%")
    assert loan_quote(space, buyer, product, ("deposit",)).total == D("18.00")


def test_amount_off_never_goes_below_zero(space_setup):
    space, manager, product = space_setup
    buyer = member(space)
    rule(space, manager, amount_off=D("500.00"))
    priced = loan_quote(space, buyer, product)
    assert priced.total == D("0.00") and priced.discount_total == D("20.00")


def test_window_inactive_archived_domain_and_switch(space_setup):
    space, manager, product = space_setup
    buyer = member(space)
    now = timezone.now()
    rule(space, manager, percent_bps=9000, starts_at=now + timedelta(days=1))
    rule(space, manager, percent_bps=9000, ends_at=now - timedelta(days=1), starts_at=now - timedelta(days=9))
    rule(space, manager, percent_bps=9000, is_active=False)
    rule(space, manager, percent_bps=9000, archived_at=now)
    rule(space, manager, percent_bps=9000, domains=["bookings"])
    assert loan_quote(space, buyer, product).discount is None
    live = rule(space, manager, percent_bps=1000)
    assert loan_quote(space, buyer, product).discount["id"] == live.pk
    switch(space, "charges.discounts", on=False)
    assert loan_quote(space, buyer, product).discount is None


def test_discounts_are_archived_never_deleted(space_setup):
    from django.core.exceptions import ValidationError

    space, manager, _product = space_setup
    with pytest.raises(ValidationError):
        rule(space, manager, percent_bps=100).delete()
