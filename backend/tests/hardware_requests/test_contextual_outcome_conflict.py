from types import SimpleNamespace

import pytest

from apps.hardware_requests.contextual_equipment_service import ProposalConflict, _require_same_outcome


@pytest.mark.parametrize(("existing", "proposed"), [
    ("request", "consumable_plan"), ("consumable_plan", "request"),
])
def test_changed_outcome_is_an_operation_conflict(existing, proposed):
    with pytest.raises(ProposalConflict, match="operation_conflict"):
        _require_same_outcome(SimpleNamespace(outcome_kind=existing), proposed)


def test_same_outcome_is_not_a_kind_conflict():
    assert _require_same_outcome(SimpleNamespace(outcome_kind="request"), "request") is None
