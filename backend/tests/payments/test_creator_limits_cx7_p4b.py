"""New paid transactions reserve capacity; existing debt seams remain ledger-first."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.utils import timezone
from rest_framework.exceptions import APIException

from apps.audit.models import AuditLog
from apps.bookings.models import Booking
from apps.bookings.services_bookings import create_booking
from apps.events.models_orders import EventOrder
from apps.events.orders_checkout import place_order
from apps.makerspaces import membership_services
from apps.makerspaces.models import MembershipRequest
from apps.payments.donations.models import Donation
from apps.payments.donations.services import create_gift
from apps.payments.models import MakerspacePaymentSettings, Payment
from apps.shop.models import ShopOrder
from apps.shop.services_pos import pos_sale
from tests.events.orders_helpers import ticketed_event, verified
from tests.limits_0120.creator_races_cx7 import race_creators
from tests.makerspaces.test_membership_admission_matrix import _setup
from tests.makerspaces.test_membership_j1 import user
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.payments.account_helpers import make_payer
from tests.payments.test_audit_0120_seams_events_shop_membership_donations import _gift_space, _donor
from tests.payments.test_charge_seams_cx11b_p2 import prepare
from tests.payments.test_track3_booking_event_charging import bookable
from tests.return_helpers import make_member, make_space
from tests.shop.helpers import line, product, shop_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_payments_ledger, pytest.mark.area_payments,
              pytest.mark.area_bookings, pytest.mark.area_events, pytest.mark.area_shop, pytest.mark.area_membership]
KINDS = ["booking", "shop", "donation", "admission", "event_order"]
KEYS = ["payments_monthly_count", "payments_monthly_amount"]


def setup(kind, key):
    if kind == "donation":
        space = _gift_space("cx7-p4b-gift")
        donors = [_donor(space, f"cx7-p4b-donor-{index}") for index in range(3)]
        create = lambda index: create_gift(space, donors[index], amount=Decimal("12.50"))
    elif kind == "shop":
        space = shop_space("cx7-p4b-pos")
        space.enabled_features = [value for value in space.enabled_features if value != "shop.cash_up"]
        actor = make_member("cx7-p4b-seller", space)
        _, variant = product(space, actor, price="12.50", stock=10)
        create = lambda index: pos_sale(space, actor=actor, lines=[line(variant)], method="cash", reference=str(index))
    elif kind == "admission":
        space, _, first, plan, _ = _setup("open", paid=True)
        plan.amount = Decimal("12.50")
        plan.save(update_fields=["amount"])
        people = [first, user("cx7-p4b-paid-applicant-1"), user("cx7-p4b-paid-applicant-2")]
        create = lambda index: membership_services.request_membership(people[index], space)
    elif kind == "event_order":
        space, event, _, ticket = ticketed_event(amount="12.50")
        people = [verified(f"cx7-p4b-order-buyer-{index}") for index in range(3)]
        create = lambda index: place_order(event, member=people[index], actor=people[index],
            request={"tickets": [{"ticket_type_id": ticket.pk, "quantity": 1}]})
    else:
        space = make_space("cx7-p4b-paid-booking")
        space.enabled_modules = sorted((set(space.enabled_modules) | {"bookings", "member_accounts"}) - {"membership"})
        space.enabled_features = ["charges.enabled", "charges.bookings"]
        people = [make_payer(f"cx7-p4b-booker-{index}", space) for index in range(3)]
        room = bookable(space, amount="12.50")
        def create(index):
            start = timezone.now() + timedelta(days=2 + index)
            return create_booking(room, member=people[index], starts_at=start, ends_at=start + timedelta(hours=1))
    space.enabled_modules = [value for value in space.enabled_modules if value != "payments"]
    space.save(update_fields=["enabled_modules", "enabled_features"])
    config = MakerspacePaymentSettings.for_makerspace(space)
    config.default_currency = "usd"
    config.save()  # for_makerspace may return an unsaved default settings instance.
    if key == "payments_monthly_amount":
        create(2)  # 12.50 used: exactly one more 12.50 transaction fits the integer cap 25.
    space.resource_limit_overrides = {key: 25 if key.endswith("amount") else 1}
    space.save(update_fields=["resource_limit_overrides"])
    return space, create


def snapshot():
    from apps.events.models_orders import EventOrderLine, EventOrderSeat
    from apps.events.models_checkout_holds import EventCheckoutHold
    from apps.makerspaces.models import MakerspaceMembership, MembershipTerm
    from apps.shop.models import ShopStockMovement, ShopVariant, ShopOrderLine, ShopCheckoutHold
    from apps.payments.models import ManualSettlement
    return [list(model.objects.order_by("pk").values()) for model in (
        Payment, AuditLog, Booking, EventOrder, EventOrderLine, EventOrderSeat, EventCheckoutHold, Donation,
        ShopOrder, ShopOrderLine, ShopVariant, ShopStockMovement, ShopCheckoutHold, ManualSettlement,
        MembershipRequest, MakerspaceMembership, MembershipTerm)]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("key", KEYS)
def test_paid_creator_max_next_exact_refusal_rolls_back_domain_and_debt(kind, key, settings):
    settings.MANAGED_PLANS_ENABLED = False
    space, create = setup(kind, key)
    create(0)
    count = 2 if key.endswith("amount") else 1
    assert Payment.objects.filter(makerspace=space).count() == count
    assert set(Payment.objects.filter(makerspace=space).values_list("provider", flat=True)) == {"unclaimed"}
    before = snapshot()
    with pytest.raises(APIException) as failure:
        create(1)
    assert (failure.value.status_code, str(failure.value.detail["code"])) == (409, "payment_quota_reached")
    assert snapshot() == before


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("key", KEYS)
def test_paid_creators_racing_for_last_capacity_admit_one(kind, key, settings):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space, create = setup(kind, key)
    assert race_creators(create) == [(201, "created"), (409, "payment_quota_reached")]
    assert Payment.objects.filter(makerspace=space).count() == (2 if key.endswith("amount") else 1)


@pytest.mark.parametrize("domain", ["loans", "machines", "events", "membership"])
def test_required_debt_seams_record_once_at_zero_transaction_limits_with_no_rail(domain, settings):
    from tests.accounts.account_factories import make_staff
    settings.MANAGED_PLANS_ENABLED = False
    space = live_space("cx7-p4b-debt-seam", set(MODULE_KEYS) - {"payments"})
    actor = make_staff(space, username="cx7-p4b-debt-manager", access_status="active")
    MakerspacePaymentSettings.objects.create(makerspace=space, default_currency="usd")
    space.resource_limit_overrides = {"payments_monthly_count": 0, "payments_monthly_amount": 0}
    space.save(update_fields=["resource_limit_overrides"])
    _, charge = prepare(space, domain, actor)
    payment = charge()
    assert (payment.amount, payment.provider, payment.status) == (Decimal("12.50"), "unclaimed", "pending")
    assert charge().pk == payment.pk
    assert Payment.objects.filter(makerspace=space).count() == 1
    assert AuditLog.objects.filter(makerspace=space, action="payment.created").count() == 1
