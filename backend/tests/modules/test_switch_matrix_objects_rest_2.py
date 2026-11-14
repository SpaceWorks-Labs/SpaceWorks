"""CX11B seeded object switch contracts, shard 3/5."""
import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import PHASES, cx11b_isolated_phase  # noqa: F401

from tests.event_reimbursements.conftest import make_world  # noqa: F401 - shared real fixture
from tests.modules.switch_matrix_object_contracts_rest import case_id, object_cases
from tests.modules.test_switch_matrix_objects_rest_support import run

pytestmark = pytest.mark.django_db(transaction=True)
CASES = object_cases(2, shards=5)
assert len(CASES) * len(PHASES) <= 150


@pytest.mark.parametrize("case", CASES, ids=[case_id(case) for case in CASES])
def test_object_switch_refuses_without_writes_and_restores_retained_data(case, make_world, monkeypatch):
    run(case, make_world, monkeypatch)

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
