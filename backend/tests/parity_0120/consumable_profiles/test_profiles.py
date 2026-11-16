"""Editing a machine type's consumable profile: validation, stock links, authority, audit (decision 341)."""
import pytest
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.audit.models import AuditLog
from apps.machines import consumable_profile_services as profiles
from apps.machines.models import MachineType
from apps.machines.models_consumable_profiles import MachineTypeConsumable
from tests.return_helpers import make_product

from .helpers import D, define, manager, pool, running_job, world

pytestmark = pytest.mark.django_db


def test_space_manager_adds_a_consumable_with_units_attributes_and_price():
    w = world("cp-add")
    row = define(w, "sheet", attributes={"material": ["Plywood", "MDF"], "thickness": []}, required=True,
                 estimate_by="staff", unit_price=D("2.500"))
    assert (row.unit, row.kind, row.required, row.unit_price) == ("sheet", "material", True, D("2.5"))
    assert AuditLog.objects.filter(action="machine_type_consumable.created", makerspace=w.space).count() == 1


@pytest.mark.parametrize("bad", [
    {"key": "Sheet"}, {"key": "sheet_id"}, {"unit": "furlong"}, {"kind": "magic"}, {"record_by": []},
    {"record_by": ["robot"]}, {"estimate_by": "oracle"}, {"attributes": {"weight": []}},
    {"attributes": {"material": ["PLA", "pla"]}},
])
def test_invalid_definitions_are_refused(bad):
    w = world("cp-bad")
    with pytest.raises(ValidationError):
        define(w, **{"key": "sheet", **bad})


def test_duplicate_key_is_refused_per_space_and_type():
    w = world("cp-dup")
    define(w, "sheet")
    with pytest.raises(ValidationError):
        define(w, "sheet")


def test_stock_link_must_match_the_unit_and_the_space():
    w = world("cp-stock")
    grams = pool(w, unit="grams")
    with pytest.raises(ValidationError):
        define(w, "sheet", unit="sheet", consumable_pool=grams)
    assert define(w, "filament", unit="kg", consumable_pool=grams).consumable_pool_id == grams.pk
    item = make_product(w.space, "Copper board")
    with pytest.raises(ValidationError):
        define(w, "board_area", unit="cm2", product=item)
    with pytest.raises(ValidationError):
        define(w, "both", unit="piece", product=item, consumable_pool=pool(w))
    other = world("cp-stock-other")
    with pytest.raises(ValidationError):
        define(w, "foreign", unit="piece", consumable_pool=pool(other))


def test_update_changes_fields_but_a_used_unit_is_frozen():
    w = world("cp-upd")
    row = define(w, "sheet")
    profiles.update(w.staff, row, {"name": "Plywood sheet", "required": True})
    row.refresh_from_db()
    assert row.name == "Plywood sheet" and row.required
    job, _ = running_job(w)
    from apps.machines.consumable_usage import record_actuals
    record_actuals(job, w.staff, [{"key": "sheet", "quantity": 1}], source="staff")
    with pytest.raises(ValidationError):
        profiles.update(w.staff, row, {"unit": "piece"})


def test_remove_deletes_an_unused_row_and_switches_off_a_used_one():
    w = world("cp-rm")
    unused, used = define(w, "spare"), define(w, "sheet")
    job, _ = running_job(w)
    from apps.machines.consumable_usage import record_actuals
    record_actuals(job, w.staff, [{"key": "sheet", "quantity": 2}], source="staff")
    assert profiles.remove(w.staff, unused) == "deleted"
    assert profiles.remove(w.staff, used) == "deactivated"
    used.refresh_from_db()
    assert not used.is_active and not MachineTypeConsumable.objects.filter(pk=unused.pk).exists()


def test_machine_manager_edits_only_types_their_scope_covers():
    w = world("cp-scope")
    other = MachineType.objects.create(makerspace=w.space, slug=f"{w.space.slug}-mill", name="Mill")
    scoped = manager(w, w.kind)
    space, kind = profiles.space_and_type(scoped, w.space.pk, w.kind.pk, write=True)
    assert kind == w.kind
    with pytest.raises(PermissionDenied):
        profiles.space_and_type(scoped, w.space.pk, other.pk, write=True)
    with pytest.raises(NotFound):
        profiles.space_and_type(scoped, w.space.pk, other.pk)


def test_a_member_and_another_space_reach_nothing():
    w = world("cp-member")
    from tests.machines.eta_helpers import owner
    with pytest.raises(NotFound):
        profiles.space_and_type(owner("cp-nobody"), w.space.pk, w.kind.pk)
    elsewhere = world("cp-elsewhere")
    with pytest.raises(NotFound):
        profiles.space_and_type(w.staff, w.space.pk, elsewhere.kind.pk)


def test_built_in_types_take_a_per_space_profile():
    w = world("cp-builtin")
    printer = MachineType.objects.get(makerspace=None, slug="3d_printer")
    space, kind = profiles.space_and_type(w.staff, w.space.pk, printer.pk, write=True)
    row = profiles.create(w.staff, space, kind, {"key": "filament", "name": "Filament", "unit": "g",
                                                 "record_by": ["staff", "adapter"]})
    second = world("cp-builtin-2")
    assert not profiles.profile(second.space, printer).exists() and row.makerspace_id == w.space.pk
