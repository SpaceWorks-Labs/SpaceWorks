"""G3 repair steps, second shard (126 cases), 481/494/520 standing."""
import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from tests.maintenance.repair_routes_cx11b_g3 import OPS, cases, run

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_inventory,
              pytest.mark.area_machines, pytest.mark.area_bookings]


@pytest.mark.parametrize("op,area,key,native", cases(OPS[7:]))
def test_repair_effect_standing_and_switch(op, area, key, native, monkeypatch, settings):
    run(op, area, key, native, monkeypatch, settings)

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
