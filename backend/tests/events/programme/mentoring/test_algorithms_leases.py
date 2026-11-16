from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
import pytest
from apps.events.mentoring.assignment_workflow import Candidate, allocate
from apps.events.mentoring.analytics import distribution, stable_due_order
from apps.events.mentoring.round_workflow import require_lease
from apps.events.contributions.errors import ProgrammeError


def test_balanced_assignment_excludes_conflicts_and_capacity_then_stable_id():
    candidates = [Candidate(2, frozenset({"pcb"}), 0, 1, frozenset()),
                  Candidate(1, frozenset({"cad"}), 0, 2, frozenset({10}))]
    result = allocate(teams={10: ["pcb"], 20: ["cad"], 30: []}, candidates=candidates, mode="round_robin")
    assert result["assignments"] == [{"team_id": 10, "mentor_assignment_id": 2},
        {"team_id": 20, "mentor_assignment_id": 1}, {"team_id": 30, "mentor_assignment_id": 1}]


def test_skill_weights_precede_load_and_unsatisfied_is_explicit():
    result = allocate(teams={1: ["pcb", "cad"], 2: ["pcb"], 3: []}, candidates=[
        Candidate(1, frozenset({"pcb"}), 1, 2, frozenset()), Candidate(2, frozenset({"cad"}), 0, 1, frozenset())],
        mode="skill_match", skill_weights={"pcb": 3, "cad": 1})
    assert result["assignments"][0]["mentor_assignment_id"] == 1
    assert result["unsatisfied_team_ids"] == [3]


def test_distribution_no_data_low_n_and_stable_spread():
    assert distribution([])["median_seconds"] is None
    assert distribution([120])["p90_seconds"] == 120
    assert distribution([10] * 10)["average_seconds"] == 10
    ids = list(range(20))
    first = stable_due_order(ids, event_id=1, round_id=2, mentor_id=3)
    assert len(first) == 8 and first == stable_due_order(list(reversed(ids)), event_id=1, round_id=2, mentor_id=3)
    assert first != stable_due_order(ids, event_id=1, round_id=2, mentor_id=4)


@pytest.mark.parametrize("change", ["mentor", "uuid", "generation", "expired"])
def test_old_tab_or_expired_lease_cannot_heartbeat_or_submit(change):
    now = datetime.now(timezone.utc)
    lease = SimpleNamespace(mentor_id=1, lease_uuid=uuid4(), generation=2, expires_at=now + timedelta(minutes=10))
    args = dict(mentor_id=1, lease_uuid=lease.lease_uuid, generation=2, at=now)
    if change == "mentor": args["mentor_id"] = 2
    elif change == "uuid": args["lease_uuid"] = uuid4()
    elif change == "generation": args["generation"] = 1
    else: args["at"] = lease.expires_at
    with pytest.raises(ProgrammeError) as error:
        require_lease(lease, **args)
    assert error.value.detail["code"] == "lease_lost"
