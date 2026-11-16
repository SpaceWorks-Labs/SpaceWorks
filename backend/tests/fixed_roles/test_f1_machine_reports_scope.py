"""Final audit 0.12.0 (M1, M2), decision 224(a): machine-area reports key to MANAGE_MACHINES and a
type-scoped Machine Manager reads only the machine types they cover."""
import pytest

from apps.accounts import rbac
from apps.machines.models import Machine
from apps.machines.report_actor_scope import actor_machine_scope
from apps.operations.report_definitions_existing import EXISTING_REPORT_DEFINITIONS
from apps.operations.reports_health import build_fablab_health
from tests.fixed_roles.test_api_area_scoping_0120_fixes import _machines_world

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("key", ["machine-usage", "maintenance-activity", "machine-service", "printer-service", "fablab-health"])
def test_machine_area_reports_are_keyed_to_manage_machines_not_view_audit(key):
    definition = next(d for d in EXISTING_REPORT_DEFINITIONS if d.key == key)
    assert definition.required_action == rbac.Action.MANAGE_MACHINES
    assert rbac.Action.VIEW_AUDIT not in definition.alternate_actions


def test_actor_machine_scope_narrows_a_type_scoped_manager_and_leaves_others_whole():
    space, laser, lathe, _machine, laser_mgr, lathe_mgr = _machines_world("f1-scope")
    assert set(actor_machine_scope(laser_mgr, space.pk)[0]) == {laser.pk}
    assert set(actor_machine_scope(lathe_mgr, space.pk)[0]) == {lathe.pk}
    assert actor_machine_scope(None, space.pk) is None
    assert actor_machine_scope(laser_mgr, None) is None


def test_fablab_health_machine_figures_are_narrowed_to_the_managers_types():
    space, laser, lathe, _machine, laser_mgr, lathe_mgr = _machines_world("f1-health")
    Machine.objects.create(makerspace=space, machine_type=lathe, name="Lathe B")
    whole = build_fablab_health(space.pk).records[0]
    mine = build_fablab_health(space.pk, actor=laser_mgr).records[0]
    other = build_fablab_health(space.pk, actor=lathe_mgr).records[0]
    assert whole["machines_active"] == 2
    assert mine["machines_active"] == 1 and other["machines_active"] == 1
