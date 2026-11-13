from decimal import Decimal

import pytest
from django.urls import reverse

from apps.machines.models import MachineConsumableAdjustment, MachineConsumablePool, MachineUsageEntry
from apps.machines.models_membership_scope import MembershipMachineTypeScope
from apps.machines.models_tracking import ConsumableCostRecord
from apps.operations.reports import report_data, report_rows
from apps.operations.reports_ab_consumables import build_consumable_usage, build_consumable_pools
from tests.analytics.ab_service_helpers import service
from tests.analytics.test_ab_inventory_m1f2 import enable
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.return_helpers import authenticated_client, make_member, make_space
from tests.test_machine_service_workflow import machine


pytestmark = pytest.mark.django_db


def pool(space, target, material="PLA", unit="grams"):
    return MachineConsumablePool.objects.create(makerspace=space, machine=target,
        material=material, unit=unit, initial_grams=1000, remaining_grams=500, low_threshold_grams=600)


def test_finalized_service_consumption_is_counted_even_when_no_reconcile_adjustment_exists():
    space = make_space("ab-consumption")
    enable(space, "machines", "machine_service")
    actor = make_member("ab-consumption-manager", space)
    target = machine(space)
    stock = pool(space, target)
    request = service(space, target, stock, actor, quantity=20)
    # A reservation equal to actual use produces no reconciliation row.
    assert MachineConsumableAdjustment.objects.get(service_request=request, kind="reserve").quantity_delta == -20
    assert not MachineConsumableAdjustment.objects.filter(service_request=request, kind="reconcile").exists()
    ConsumableCostRecord.objects.create(makerspace=space, source_kind="pooled_service", source_id=request.pk,
        quantity=20, measurement_unit="grams", unit_price_minor_per_measurement_unit=2,
        cost_total_minor=40, currency="USD")
    # Printer/manual facts already represented by adjustments are never added directly.
    usage = MachineUsageEntry.objects.create(machine=target, hours=1, consumed_grams=100,
        consumed_quantity=100, logged_by=actor)
    adjustment = MachineConsumableAdjustment.objects.create(makerspace=space, consumable_pool=stock,
        kind="manual", quantity_delta=-5, usage_entry=usage)
    ConsumableCostRecord.objects.create(makerspace=space, source_kind="manual_adjustment", source_id=adjustment.pk,
        quantity=5, measurement_unit="grams", unit_price_minor_per_measurement_unit=3,
        cost_total_minor=15, currency="INR")
    # Keep adjustments separate without adding a reconciliation to the service
    # whose finalized quantity must be counted in the absence of such a row.
    MachineConsumableAdjustment.objects.create(makerspace=space, consumable_pool=stock,
        kind="correction", quantity_delta=3)
    service(space, target, stock, actor, quantity=7, status="in_progress")
    rows = build_consumable_usage(space.pk, actor=actor).records
    assert sum(row["consumed_quantity"] for row in rows) == 25
    assert sum(row["reserved_quantity"] for row in rows) == 7
    assert sum(row["adjusted_quantity"] for row in rows) == 3
    assert {(row["currency"], row["cost_total_minor"]) for row in rows if row["cost_total_minor"]} == {("USD", 40), ("INR", 15)}
    assert_report_disclosure_safe(rows)


@pytest.mark.parametrize("measurement,product_present", [("count", True), ("grams", False)])
def test_non_pool_rows_with_or_without_product_are_authoritative(measurement, product_present):
    from apps.machines.models import MachineConsumable
    from tests.return_helpers import make_product
    space = make_space("ab-non-pool")
    enable(space, "machines", "machine_service")
    actor = make_member("ab-non-pool-manager", space)
    target = machine(space)
    product = make_product(space) if product_present else None
    consumable = MachineConsumable.objects.create(machine=target, measurement=measurement,
        product=product, label="Material", remaining=100)
    service(space, target, None, actor,
            consumptions=[{"machine_consumable_id": consumable.pk, "quantity": 4}])
    rows = build_consumable_usage(space.pk, actor=actor).records
    assert len(rows) == 1 and rows[0]["consumed_quantity"] == 4
    assert rows[0]["cost_unknown_quantity"] == 4 and rows[0]["measurement_unit"] == measurement
    assert rows[0]["source"] == "non_pool_consumption"
    assert_report_disclosure_safe(rows)


def test_machine_type_scope_applies_to_preview_export_and_pool_depletion():
    space, other = make_space("ab-machine-scope"), make_space("ab-machine-other")
    enable(space, "machines", "machine_service")
    enable(other, "machines", "machine_service")
    from tests.fixed_roles.helpers import staff_account
    actor = staff_account(space, "ab-machine-manager", "machine_manager")
    from apps.makerspaces.models import MakerspaceMembership
    membership = MakerspaceMembership.all_tracks.get(user=actor, makerspace=space)
    allowed, forbidden = machine(space, "Allowed"), machine(space, "Forbidden")
    MembershipMachineTypeScope.objects.create(membership=membership, machine_type=allowed.machine_type)
    for owner, target, material in ((space, allowed, "Allowed"), (space, forbidden, "Forbidden"),
                                    (other, machine(other), "FOREIGN")):
        stock = pool(owner, target, material)
        service(owner, target, stock, actor)
    for key in ("consumable-usage", "consumable-pools"):
        response = report_data(key, space.pk, actor=actor)
        assert {row["material"] for row in response["typed_rows"]} == {"Allowed"}
        exported = report_rows(key, space.pk, actor=actor)
        assert "Forbidden" not in str(exported) and "FOREIGN" not in str(exported)
        assert_report_disclosure_safe(response)
        assert_report_disclosure_safe(exported)
        client_response = authenticated_client(actor).get(reverse("analytics-generic", args=[space.pk, key]))
        assert client_response.status_code == 200
        assert {row["material"] for row in client_response.data["typed_rows"]} == {"Allowed"}
    MembershipMachineTypeScope.objects.filter(membership=membership).delete()
    assert build_consumable_usage(space.pk, actor=actor).records == []
    assert build_consumable_pools(space.pk, actor=actor).records == []


@pytest.mark.parametrize("grain", ["day", "week", "month"])
def test_units_and_failed_partial_consumption_stay_separate(grain):
    space = make_space("ab-units")
    enable(space, "machines", "machine_service")
    actor = make_member("ab-unit-manager", space)
    target = machine(space)
    service(space, target, pool(space, target, "Solid", "grams"), actor, quantity=2, status="failed")
    service(space, target, pool(space, target, "Liquid", "milliliters"), actor, quantity=3)
    rows = build_consumable_usage(space.pk, actor=actor, grain=grain).records
    assert {(r["measurement_unit"], r["consumed_quantity"]) for r in rows} == {("grams", Decimal(2)), ("milliliters", Decimal(3))}
    assert sum(row["cost_unknown_quantity"] for row in rows) == 5
    assert_report_disclosure_safe(rows)
