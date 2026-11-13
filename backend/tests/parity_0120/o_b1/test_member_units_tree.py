"""O-B1: the unit tree -- levels, codes, paths, move, archive, limit, audit (service level)."""
import pytest

from apps.audit.models import AuditLog
from apps.makerspaces import member_units
from apps.makerspaces.member_units import UnitError
from apps.makerspaces.membership_join_units import plans_for_unit
from apps.makerspaces.models import MemberUnit, MembershipPlan
from apps.makerspaces.models_member_units import PlanUnit
from tests.makerspaces.l4_helpers import features_off, plan
from tests.parity_0120.o_b1.helpers import tree, units_space

pytestmark = pytest.mark.django_db(transaction=True)


def test_codes_are_generated_deduplicated_and_paths_are_code_paths():
    space, boss = units_space("ob1-codes")
    first = member_units.create_unit(boss, space, name="Kerala State Chapter")
    second = member_units.create_unit(boss, space, name="Kerala State Chapter")
    assert first.code == "KERALA" and second.code == "KERAL2"
    assert first.path == "/KERALA/" and first.level == 0
    child = member_units.create_unit(boss, space, name="Kochi", parent_id=first.pk)
    assert child.path == "/KERALA/KOCHI/" and child.level == 1


def test_named_levels_cap_the_depth_and_cannot_drop_a_used_level():
    space, boss = units_space("ob1-depth")
    _south, kochi, _north = tree(boss, space)
    with pytest.raises(UnitError) as error:
        member_units.create_unit(boss, space, name="Too deep", parent_id=kochi.pk)
    assert error.value.detail["code"] == "member_unit_depth"
    with pytest.raises(UnitError) as error:
        member_units.set_level_names(boss, space, ["Region"])
    assert error.value.detail["code"] == "member_unit_levels_in_use"
    assert member_units.level_names(space) == ["Region", "District"]


def test_code_is_validated_unique_and_locked_once_in_use():
    space, boss = units_space("ob1-code-lock")
    south, _kochi, north = tree(boss, space)
    with pytest.raises(UnitError) as error:
        member_units.update_unit(boss, north, {"code": "south"})
    assert error.value.detail["code"] == "member_unit_code_taken"
    with pytest.raises(UnitError) as error:
        member_units.update_unit(boss, north, {"code": "bad code"})
    assert error.value.detail["code"] == "member_unit_code_invalid"
    with pytest.raises(UnitError) as error:  # a unit with children: its code is part of their paths
        member_units.update_unit(boss, south, {"code": "SOUTH2"})
    assert error.value.detail["code"] == "member_unit_code_locked"
    assert member_units.update_unit(boss, north, {"code": "N1"}).path == "/N1/"


def test_move_rewrites_the_subtree_and_refuses_cycles_and_depth():
    space, boss = units_space("ob1-move")
    south, kochi, north = tree(boss, space)
    with pytest.raises(UnitError) as error:
        member_units.move_unit(boss, south, kochi.pk)
    assert error.value.detail["code"] == "member_unit_cycle"
    with pytest.raises(UnitError) as error:  # south + kochi under north would need three levels
        member_units.move_unit(boss, south, north.pk)
    assert error.value.detail["code"] == "member_unit_depth"
    moved = member_units.move_unit(boss, kochi, north.pk)
    assert moved.path == "/NORTH/KOCHI/" and moved.parent_id == north.pk and moved.level == 1


def test_archive_needs_empty_children_hides_from_the_tree_and_restores():
    space, boss = units_space("ob1-archive")
    south, kochi, _north = tree(boss, space)
    with pytest.raises(UnitError) as error:
        member_units.archive_unit(boss, south)
    assert error.value.detail["code"] == "member_unit_has_children"
    member_units.archive_unit(boss, kochi)
    assert [row["code"] for row in member_units.tree(space)] == ["NORTH", "SOUTH"]
    with pytest.raises(UnitError):
        member_units.create_unit(boss, space, name="Under archived", parent_id=kochi.pk)
    member_units.archive_unit(boss, south)
    with pytest.raises(UnitError):  # the parent is archived
        member_units.restore_unit(boss, kochi)


def test_payment_instructions_come_from_the_nearest_ancestor():
    space, boss = units_space("ob1-pay")
    south, kochi, _north = tree(boss, space)
    assert member_units.effective_payment_instructions(kochi) == ("", None)
    member_units.update_unit(boss, south, {"payment_instructions": "UPI south@bank"})
    text, source = member_units.effective_payment_instructions(MemberUnit.objects.get(pk=kochi.pk))
    assert text == "UPI south@bank" and source.pk == south.pk


def test_the_member_units_limit_is_a_typed_409():
    space, boss = units_space("ob1-limit")
    space.resource_limit_overrides = {"member_units": 1}
    space.save(update_fields=["resource_limit_overrides"])
    member_units.create_unit(boss, space, name="One")
    with pytest.raises(Exception) as error:
        member_units.create_unit(boss, space, name="Two")
    assert getattr(error.value, "code", "") == "member_units_quota_reached"


def test_writes_are_refused_while_the_switch_is_off_and_audit_carries_ids_only():
    space, boss = units_space("ob1-off")
    unit = member_units.create_unit(boss, space, name="Secret Name")
    row = AuditLog.objects.filter(action="member_unit.created", makerspace=space).get()
    assert "Secret Name" not in str(row.meta) and row.meta["unit_id"] == unit.pk
    features_off(space, "unit_scoped_staff", "units")
    with pytest.raises(Exception) as error:
        member_units.create_unit(boss, space, name="Nope")
    assert getattr(error.value, "status_code", None) == 404


def test_plans_for_unit_inherit_down_the_subtree():
    space, boss = units_space("ob1-plans")
    south, kochi, north = tree(boss, space)
    everywhere, southern = plan(space, "Everywhere"), plan(space, "Southern", amount="5.00")
    PlanUnit.objects.create(makerspace=space, plan=southern, unit=south)
    all_plans = MembershipPlan.objects.filter(makerspace=space)
    assert set(plans_for_unit(all_plans, kochi)) == {everywhere, southern}
    assert set(plans_for_unit(all_plans, north)) == {everywhere}
    assert set(plans_for_unit(all_plans, None)) == {everywhere}
