"""G3 adapter administration, second shard (102 cases)."""
import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from tests.devices.admin_routes_cx11b_g3 import OPS, keys, run

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_devices, pytest.mark.area_machines]
CASES = [(op, key, native) for op in OPS[13:] for key in keys(op) for native in (False, True)]


@pytest.mark.parametrize("op,key,native", CASES)
def test_adapter_admin_effect_standing_and_switch(op, key, native, monkeypatch):
    run(op, key, native, monkeypatch)

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
