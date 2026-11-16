"""L6 G29: tiers, pay-what-you-want, group seats, access codes, promo limits, booking fee."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.events.models import EventOrder
from apps.events.promos import create_promo
from apps.events.ticketing import create_ticket
from tests.events.orders_helpers import order_payment, place, quote, settings_for, ticketed_event, verified

pytestmark = pytest.mark.django_db


def _t(ticket, quantity=1, **extra):
    return {"ticket_type_id": ticket.pk, "quantity": quantity, **extra}


def test_tier_chain_opens_next_tier_on_sell_out(django_capture_on_commit_callbacks):
    space, event, staff, early = ticketed_event(amount=5, ticket_capacity=1, tier_group="main", tier_rank=0)
    regular = create_ticket(event, actor=staff, name="Regular", amount=Decimal(9), tier_group="main", tier_rank=1)
    buyer = verified("buyer")
    assert quote(buyer, event, [_t(regular)]).data["code"] == "sold_out"
    with django_capture_on_commit_callbacks(execute=True):
        assert place(buyer, event, [_t(early)]).status_code == 201
    assert quote(verified("two"), event, [_t(regular)]).data["quote"]["total"] == "9.00"


def test_tier_opens_when_earlier_tier_sales_end():
    space, event, staff, early = ticketed_event(amount=5, tier_group="main", tier_rank=0,
                                                sales_end_at=timezone.now() + timedelta(hours=1))
    regular = create_ticket(event, actor=staff, name="Regular", amount=Decimal(9), tier_group="main", tier_rank=1)
    buyer = verified("buyer")
    assert quote(buyer, event, [_t(regular)]).status_code == 409
    type(early).objects.filter(pk=early.pk).update(sales_end_at=timezone.now() - timedelta(seconds=1))
    assert quote(buyer, event, [_t(regular)]).status_code == 200


def test_pay_what_you_want_minimum_and_group_seats():
    space, event, staff, pwyw = ticketed_event(amount=10, pricing_mode="pwyw", min_amount=Decimal(3))
    group = create_ticket(event, actor=staff, name="Family", amount=Decimal(20), seats_per_ticket=4)
    buyer = verified("buyer")
    low = quote(buyer, event, [_t(pwyw, amount="2.00")])
    assert low.status_code == 400 and low.data["code"] == "amount_below_minimum"
    assert quote(buyer, event, [_t(pwyw, amount="7.50")]).data["quote"]["total"] == "7.50"
    response = place(buyer, event, [_t(group)])
    assert response.status_code == 201
    assert EventOrder.objects.get().seats.count() == 4
    assert order_payment(EventOrder.objects.get()).amount == Decimal("20.00")


def test_hidden_ticket_needs_a_valid_access_code():
    space, event, staff, _general = ticketed_event(amount=10)
    secret = create_ticket(event, actor=staff, name="Crew", amount=Decimal(0), is_hidden=True)
    _promo, code = create_promo(event, actor=staff, kind="access", ticket_type_id=secret.pk, max_uses=5)
    buyer = verified("buyer")
    assert quote(buyer, event, [_t(secret)]).data["code"] == "sold_out"
    bad = quote(buyer, event, [_t(secret)], access_codes=["nope-nope-nope"])
    assert bad.status_code == 404 and bad.data["code"] == "access_code_invalid"
    assert quote(buyer, event, [_t(secret)], access_codes=[code]).status_code == 200


def test_quantity_rules_and_event_order_limit():
    space, event, staff, ticket = ticketed_event(amount=10, min_quantity=2, per_order_limit=3)
    buyer = verified("buyer")
    assert quote(buyer, event, [_t(ticket, 1)]).data["code"] == "order_limit"
    assert quote(buyer, event, [_t(ticket, 4)]).data["code"] == "order_limit"
    settings_for(event, max_tickets_per_order=2)
    assert quote(buyer, event, [_t(ticket, 3)]).data["code"] == "order_limit"
    assert quote(buyer, event, [_t(ticket, 2)]).status_code == 200


def test_promo_per_ticket_and_per_order_and_booking_fee():
    space, event, staff, ticket = ticketed_event(amount=10)
    _per_ticket, ticket_code = create_promo(event, actor=staff, code="EACHTICKET", percent_off=10, max_uses=5)
    _per_order, order_code = create_promo(event, actor=staff, code="WHOLEORDER", amount_off=5, max_uses=5,
                                          applies_per="order")
    buyer = verified("buyer")
    assert quote(buyer, event, [_t(ticket, 3)], promo_code=ticket_code).data["quote"]["total"] == "27.00"
    assert quote(buyer, event, [_t(ticket, 3)], promo_code=order_code).data["quote"]["total"] == "25.00"
    settings_for(event, booking_fee_fixed=Decimal("1.00"), booking_fee_bps=500)
    preview = quote(buyer, event, [_t(ticket, 2)])
    # 20.00 + 1.00 fixed + 5% of 20.00
    assert preview.data["quote"]["total"] == "22.00"
    assert [line["component"] for line in preview.data["quote"]["lines"]][-1] == "booking_fee"
    place(buyer, event, [_t(ticket, 3)], promo_code=ticket_code)
    _per_ticket.refresh_from_db()
    assert _per_ticket.uses == 3


def test_member_only_ticket_admits_the_buyer_alone():
    from tests.events.collab_helpers import make_member
    from tests.events.orders_helpers import l6_space
    space = l6_space(membership=True)
    _space, event, staff, member_ticket = ticketed_event(space, amount=5, audience="member")
    member = make_member(space)
    assert quote(member, event, [_t(member_ticket, 2)]).data["code"] == "order_limit"
    assert quote(member, event, [_t(member_ticket, 1)]).status_code == 200
