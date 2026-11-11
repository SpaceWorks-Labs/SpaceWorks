"""P2-2 (#84/#85, #159, decision 216): the one best member discount on room bookings.

The booking quote, the staff price confirmation and the frozen pending snapshot all
come from `payments.pricing.quote()`, so a discount is shown, bound and frozen once.
"""

from decimal import Decimal

import pytest

from apps.bookings.models import Booking
from apps.bookings.service_payments import booking_quote, charged_quote
from apps.bookings.staff_price_confirmation import confirmation_digest, confirmed_quote
from apps.makerspaces.models import MakerspaceMembership
from apps.payments.models import PriceDiscount
from tests.bookings.test_staff_price_confirmation import booking_debts, create, preview, setup, window
from tests.machines.certification_helpers import _member
from tests.payments.pricing.helpers import plan, put_on_plan
from tests.return_helpers import make_user

pytestmark = pytest.mark.django_db
D = Decimal


def discounted(slug, approval="instant"):
    maker, actor, member, room, client = setup(slug, approval=approval)
    maker.enabled_features = sorted(set(maker.enabled_features) | {"charges.pricing", "charges.discounts"})
    maker.save(update_fields=["enabled_features"])
    return maker, actor, member, room, client


def rule(maker, creator, audience="all_members", **fields):
    return PriceDiscount.objects.create(makerspace=maker, name=fields.pop("name", "Rule"), audience=audience,
                                        created_by=creator, **fields)


def quoted(room, who, body):
    from django.utils.dateparse import parse_datetime
    probe = Booking(space=room, member=who, starts_at=parse_datetime(body["starts_at"]),
                    ends_at=parse_datetime(body["ends_at"]))
    return booking_quote(probe, who)


def test_members_get_the_discount_and_non_or_revoked_members_do_not():
    maker, actor, member, room, _ = discounted("bk-disc-who")
    rule(maker, actor, percent_bps=2000)
    body = window(member)
    assert quoted(room, member, body).total == D("10.00")
    outsider = make_user("bk-disc-outsider")
    assert quoted(room, outsider, body).discount is None and quoted(room, outsider, body).total == D("12.50")
    MakerspaceMembership.objects.filter(makerspace=maker, user=member).update(status="revoked")
    assert quoted(room, member, body).total == D("12.50")


def test_one_best_rule_wins_and_nothing_stacks():
    maker, actor, member, room, _ = discounted("bk-disc-best")
    pro = plan(maker)
    put_on_plan(maker, member, pro)
    rule(maker, actor, percent_bps=1000, name="Everyone 10%")
    best = rule(maker, actor, audience="plan", plan=pro, percent_bps=2500, name="Pro 25%")
    rule(maker, actor, audience="member", member=member, amount_off=D("3.00"), name="Three off")
    rule(maker, actor, percent_bps=9000, domains=["loans"], name="Loans only")
    priced = quoted(room, member, window(member))
    assert priced.discount["id"] == best.pk
    assert priced.total == D("9.37")  # 12.50 - 3.125 rounded half-up; never 25% + 10% + 3.00


def test_discount_above_the_price_makes_the_booking_free_and_raises_no_debt():
    maker, actor, member, room, client = discounted("bk-disc-free")
    rule(maker, actor, audience="member", member=member, amount_off=D("50.00"))
    body = window(member)
    shown = preview(client, room, body)
    assert D(shown.data["quote"]["total"]) == D("0.00")
    response = create(client, room, {**body, "price_confirmation": shown.data["price_confirmation"]})
    assert response.status_code == 201 and not booking_debts(maker).exists()


def test_staff_confirmation_digest_moves_with_the_discount():
    maker, actor, member, room, client = discounted("bk-disc-digest")
    body = window(member)
    plain = preview(client, room, body)
    discount = rule(maker, actor, percent_bps=2000)
    shown = preview(client, room, body)
    assert shown.data["price_confirmation"] != plain.data["price_confirmation"]
    assert D(shown.data["quote"]["total"]) == D("10.00") and shown.data["quote"]["discount"]["id"] == discount.pk
    stale = create(client, room, {**body, "price_confirmation": plain.data["price_confirmation"]})
    assert stale.status_code == 409 and stale.data["code"] == "price_changed"
    assert not Booking.objects.exists()
    response = create(client, room, {**body, "price_confirmation": shown.data["price_confirmation"]})
    assert response.status_code == 201
    debt = booking_debts(maker).get()
    assert debt.amount == D("10.00") and debt.pricing_snapshot["discount"]["id"] == discount.pk


def test_digest_binds_which_rule_applied_not_only_the_total():
    maker, actor, member, room, _ = discounted("bk-disc-rule")
    other, _ = _member(maker, "bk-disc-rule-other")
    first = rule(maker, actor, audience="member", member=member, percent_bps=2000, name="A")
    body = window(member)
    from django.utils.dateparse import parse_datetime
    start, end = parse_datetime(body["starts_at"]), parse_datetime(body["ends_at"])
    before = confirmation_digest(room, member, start, end, *confirmed_quote(room, member, start, end))
    PriceDiscount.objects.filter(pk=first.pk).update(is_active=False)
    rule(maker, actor, audience="member", member=member, percent_bps=2000, name="B")
    after = confirmation_digest(room, member, start, end, *confirmed_quote(room, member, start, end))
    assert before != after
    assert confirmed_quote(room, other, start, end)[1].discount is None


def test_pending_booking_freezes_the_discounted_quote_through_approval():
    maker, actor, member, room, client = discounted("bk-disc-pending", approval="approve")
    discount = rule(maker, actor, percent_bps=2000)
    body = window(member)
    shown = preview(client, room, body)
    response = create(client, room, {**body, "price_confirmation": shown.data["price_confirmation"]})
    assert response.status_code == 201
    booking = Booking.objects.get(pk=response.data["id"])
    assert booking.status == Booking.Status.PENDING
    assert booking.pricing_snapshot["discount"]["id"] == discount.pk
    assert D(booking.pricing_snapshot["total"]) == D("10.00")
    PriceDiscount.objects.filter(pk=discount.pk).update(is_active=False)
    assert booking_quote(booking).total == D("12.50")
    assert charged_quote(booking, actor, approval=True).total == D("10.00")
