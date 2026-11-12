"""Migration 0042 seeds profiles from existing data without loss, and the per-type report (decision 341)."""
from importlib import import_module

import pytest
from django.apps import apps

from apps.machines.models import MachineConsumable, MachineMaterial, MachineType
from apps.machines.models_consumable_profiles import MachineTypeConsumable
from apps.machines import consumable_usage as usage
from tests.return_helpers import make_product

from .helpers import D, define, pool, running_job, world

pytestmark = pytest.mark.django_db
migration = import_module("apps.machines.migrations.0042_seed_consumable_profiles")


def run():
    migration.seed(apps, None)


def rows(w, kind=None):
    return {row.key: row for row in MachineTypeConsumable.objects.filter(makerspace=w.space,
                                                                         machine_type=kind or w.kind)}


def test_per_machine_consumables_become_type_profile_rows():
    w = world("seed-mc")
    machine = w.machines[0]
    item = make_product(w.space, "Copper board")
    MachineConsumable.objects.create(machine=machine, measurement="grams", label="Spare PLA", remaining=D("500"))
    MachineConsumable.objects.create(machine=machine, measurement="count", product=item)
    MachineConsumable.objects.create(machine=w.machines[1], measurement="grams", label="Spare PLA")
    run()
    seeded = rows(w)
    assert set(seeded) == {"spare_pla", "copper_board"}
    assert seeded["spare_pla"].unit == "g" and seeded["copper_board"].unit == "piece"
    assert seeded["copper_board"].product_id == item.pk and seeded["spare_pla"].unit_price is None
    assert MachineConsumable.objects.count() == 3  # nothing moved or deleted


def test_a_material_catalogue_becomes_the_primary_material_row_in_the_metering_unit():
    w = world("seed-mat")
    MachineType.objects.filter(pk=w.kind.pk).update(capability_config={"metering_unit": "length",
                                                                        "requires_booking": False})
    MachineMaterial.objects.create(makerspace=w.space, machine_type=w.kind, name="Adhesive vinyl",
                                   colours=["Red", "Blue"])
    MachineMaterial.objects.create(makerspace=w.space, machine_type=w.kind, name="Heat-transfer vinyl",
                                   colours=["red", "White"])
    run()
    material = rows(w)["material"]
    assert material.unit == "mm" and material.kind == "material" and not material.required
    assert material.attributes == {"material": ["Adhesive vinyl", "Heat-transfer vinyl"],
                                   "colour": ["Red", "Blue", "White"]}
    assert material.estimate_by == "staff" and material.record_by == ["staff", "adapter"]


def test_a_pool_scoped_to_a_type_seeds_its_unit_when_the_type_has_no_metering():
    w = world("seed-pool")
    p = pool(w, unit="milliliters", initial="1000", material="Resin")
    type(p).objects.filter(pk=p.pk).update(machine_type=w.kind)
    run()
    assert rows(w)["material"].unit == "ml"


def test_the_seed_is_idempotent_and_leaves_hand_made_rows_alone():
    w = world("seed-again")
    MachineMaterial.objects.create(makerspace=w.space, machine_type=w.kind, name="PLA", colours=["Black"])
    MachineType.objects.filter(pk=w.kind.pk).update(capability_config={"metering_unit": "weight",
                                                                        "requires_booking": False})
    define(w, "nozzle", kind="tool_wear", unit="h")
    run()
    run()
    assert sorted(rows(w)) == ["material", "nozzle"]


def test_types_a_space_does_not_price_by_material_get_nothing():
    w = world("seed-none")
    run()
    assert rows(w) == {}


def test_report_sums_estimates_and_actuals_per_type_and_key():
    from apps.operations.reports import report_rows
    w = world("rep")
    define(w, "sheet", unit_price=D("2.00"), estimate_by="staff")
    first, _ = running_job(w)
    usage.record_estimates(first, w.staff, [{"key": "sheet", "quantity": 1}], source="staff")
    usage.record_estimates(first, w.staff, [{"key": "sheet", "quantity": 3}], source="staff")
    usage.record_actuals(first, w.staff, [{"key": "sheet", "quantity": 2}], source="staff")
    second, _ = running_job(w)
    usage.record_actuals(second, None, [{"key": "sheet", "quantity": 1}], source="adapter")
    from apps.machines.models import MachineServiceRequest
    w.space.enabled_modules = sorted({*w.space.enabled_modules, "reports"})
    w.space.save(update_fields=["enabled_modules"])
    [row] = report_rows("machine-consumables", w.space.pk, actor=w.staff)
    assert (row["key"], row["unit"], row["jobs"]) == ("sheet", "sheet", 2)
    assert D(row["estimated_quantity"]) == 3 and D(row["actual_quantity"]) == 3 and D(row["adapter_quantity"]) == 1
    assert D(row["actual_value"]) == D("6.00")
    assert MachineServiceRequest.objects.filter(makerspace=w.space).count() == 2
