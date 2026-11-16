"""Lane L15: the one resolver -- precedence, caps, grace, increment, minimum, rounding."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.machines.models import MakerspaceMachineTypePricing
from apps.payments.models import MakerspacePaymentSettings, PriceOverride
from apps.payments.pricing import quote, verify_digest
from apps.payments.pricing.errors import PriceChanged
from tests.payments.pricing.helpers import D, pricing_space, rate, switch
from tests.return_helpers import make_product

pytestmark = pytest.mark.django_db
T = PriceOverride.TargetType


def override(space, product, component, mode, amount=None, cap=None):
    return PriceOverride.objects.create(makerspace=space, domain="loans", component=component,
                                        target_type=T.INVENTORY_PRODUCT, product=product, mode=mode,
                                        amount=None if amount is None else D(amount),
                                        cap=None if cap is None else D(cap))


def test_rental_per_unit_cap_and_per_loan_fee():
    space, _ = pricing_space("pr-rental")
    product = make_product(space)
    rate(space, "loans", rental_per_loan="1.25", rental_per_day=("2.50", {"cap": D("6.00")}))
    priced = quote(space, "loans", params={"items": [(product, 2)], "days": 3, "components": ("rental",)})
    by = {line.component: line for line in priced.lines}
    assert by["rental_per_loan"].gross == D("2.50")
    assert by["rental_per_day"].gross == D("12.00") and by["rental_per_day"].cap_applied
    assert priced.total == D("14.50")


def test_override_precedence_free_custom_and_free_mode():
    space, _ = pricing_space("pr-precedence")
    free_item, custom_item, plain = (make_product(space, name=name) for name in ("Free", "Custom", "Plain"))
    rate(space, "loans", rental_per_day="2.00")
    override(space, free_item, "rental_per_day", "free")
    override(space, custom_item, "rental_per_day", "custom", "5.00")
    items = [(free_item, 1), (custom_item, 1), (plain, 1)]
    priced = quote(space, "loans", params={"items": items, "days": 1, "components": ("rental",)})
    assert [(line.target["id"], line.gross, line.source) for line in priced.lines] == [
        (custom_item.pk, D("5.00"), "override"), (plain.pk, D("2.00"), "default")]
    rate(space, "loans", mode="free")
    priced = quote(space, "loans", params={"items": items, "days": 1, "components": ("rental",)})
    assert [(line.target["id"], line.gross) for line in priced.lines] == [(custom_item.pk, D("5.00"))]


def test_legacy_item_deposit_is_custom_and_zero_inherits():
    space, _ = pricing_space("pr-deposit", loan_deposit_mode=MakerspacePaymentSettings.LoanDepositMode.PER_PRODUCT)
    priced_item = make_product(space, name="Scope", deposit_amount=D("4.00"))
    zero_item = make_product(space, name="Probe", deposit_amount=D("0"))
    priced = quote(space, "loans", params={"items": [(priced_item, 2), (zero_item, 1)], "components": ("deposit",)})
    assert priced.total == D("8.00") and priced.lines[0].source == "item"


def test_late_fee_uses_the_highest_item_rate_with_space_grace_and_cap():
    space, _ = pricing_space("pr-late", loan_late_fee_per_day=D("1.00"), loan_grace_days=1,
                             loan_late_fee_cap=D("20.00"))
    cheap, dear = make_product(space, name="Cheap"), make_product(space, name="Dear")
    override(space, dear, "late_per_day", "custom", "3.00", cap="7.00")
    now = timezone.now()
    priced = quote(space, "loans", params={"items": [(cheap, 1), (dear, 1)], "components": ("late",),
                                           "due_at": now - timedelta(days=5), "now": now})
    line = priced.lines[0]
    assert (line.unit_amount, line.quantity, line.gross) == (D("3.00"), D(4), D("7.00"))
    assert line.target["id"] == dear.pk


def test_pricing_switch_off_is_release_one():
    space, _ = pricing_space("pr-off", loan_late_fee_per_day=D("2.00"))
    product = make_product(space)
    rate(space, "loans", rental_per_day="9.00")
    override(space, product, "late_per_day", "custom", "50.00")
    switch(space, "charges.pricing", on=False)
    now = timezone.now()
    priced = quote(space, "loans", params={"items": [(product, 1)], "days": 3, "due_at": now - timedelta(days=2),
                                           "now": now})
    assert [(line.component, line.gross) for line in priced.lines] == [("late_per_day", D("4.00"))]


def test_machine_time_increment_minimum_material_and_per_job(machine_setup):
    space, machine, pool = machine_setup
    rate(space, "machines", time=("6.00", {"billing_increment": 15, "minimum": 30}), material="0.10",
         per_job="1.00")
    priced = quote(space, "machines", params={"machine": machine, "pool": pool, "minutes": 31, "quantity": D("12")})
    by = {line.component: line for line in priced.lines}
    assert by["time"].detail["billed_minutes"] == 45 and by["time"].gross == D("4.50")
    assert by["material"].gross == D("1.20") and by["per_job"].gross == D("1.00")
    short = quote(space, "machines", params={"machine": machine, "minutes": 5})
    assert {line.component: line.gross for line in short.lines}["time"] == D("3.00")


def test_machine_type_row_is_the_middle_level_and_matches_release_one(machine_setup):
    space, machine, _pool = machine_setup
    machine.machine_type.capability_config = {"metering_unit": "minutes"}
    machine.machine_type.save()
    MakerspaceMachineTypePricing.objects.create(makerspace=space, machine_type=machine.machine_type,
                                                rate_per_unit=D("0.07"), flat_fee=D("2.00"), payment_enabled=True)
    priced = quote(space, "machines", params={"machine": machine, "minutes": 7})
    assert priced.total == D("2.49")  # 0.07 x 7 + 2.00, as release 1 charged it
    rate(space, "machines", material="0.50")
    combined = quote(space, "machines", params={"machine": machine, "minutes": 7, "quantity": D("4")})
    assert combined.total == D("4.49")


def test_failed_job_charges_none_material_only_or_full(machine_setup):
    space, machine, pool = machine_setup
    rate(space, "machines", time="6.00", material="0.10", per_job="1.00")
    params = {"machine": machine, "pool": pool, "minutes": 10, "quantity": D("10"), "outcome": "failed"}
    assert quote(space, "machines", params=params).total == 0
    assert quote(space, "machines", params={**params, "failure_charge": "material_only"}).total == D("1.00")
    assert quote(space, "machines", params={**params, "failure_charge": "full"}).total == D("3.00")


def test_half_up_rounding_per_line():
    from apps.bookings.models import BookableSpace

    space, _ = pricing_space("pr-round")
    room = BookableSpace.objects.create(makerspace=space, name="Studio")
    rate(space, "bookings", per_hour=("0.15", {"billing_increment": 1}))
    start = timezone.now()
    priced = quote(space, "bookings", room, params={"starts_at": start, "ends_at": start + timedelta(minutes=10)})
    assert priced.total == D("0.03")  # 0.025 rounds half-up, never to even


def test_digest_moves_with_the_price_and_verify_refuses():
    space, _ = pricing_space("pr-digest")
    product = make_product(space)
    rate(space, "loans", rental_per_day="2.00")
    params = {"items": [(product, 1)], "days": 2, "components": ("rental",)}
    first = quote(space, "loans", params=params)
    assert verify_digest(quote(space, "loans", params=params), first.digest)
    rate(space, "loans", rental_per_day="3.00")
    with pytest.raises(PriceChanged) as caught:
        verify_digest(quote(space, "loans", params=params), first.digest)
    assert caught.value.detail["code"] == "price_changed"
    assert Decimal(caught.value.detail["quote"]["total"]) == D("6.00")


@pytest.fixture
def machine_setup():
    from apps.machines.models import Machine, MachineConsumablePool, MachineType

    space, _ = pricing_space("pr-machines")
    machine_type = MachineType.objects.create(makerspace=space, name="Laser", slug="laser-pr")
    machine = Machine.objects.create(makerspace=space, machine_type=machine_type, name="Laser 1")
    pool = MachineConsumablePool.objects.create(makerspace=space, machine=machine, material="Acrylic",
                                                initial_grams=D("1000"), remaining_grams=D("1000"))
    return space, machine, pool
