"""E-B4 (D10): the assignment preview's loads, keep/replace split and plan fingerprint."""
from types import SimpleNamespace

import pytest

from apps.events.judging.assignment_preview import (
    loads_before, plan_fingerprint, replaceable_pairs, require_fresh, split_plan)
from apps.events.judging.errors import ProgrammeError

ROUND = SimpleNamespace(pk=7, version=3)
VALUES = {"strategy": "balanced", "seed": "0", "max_load": 10, "existing": "keep"}


def row(pk, snapshot, judge, state="assigned"):
    return SimpleNamespace(pk=pk, submission_snapshot_id=snapshot, judge_role_assignment_id=judge, state=state)


def test_loads_before_counts_every_judge_including_idle_ones():
    assert loads_before({(1, 10), (2, 10), (3, 11)}, {10, 11, 12}) == {"10": 2, "11": 1, "12": 0}


def test_replace_touches_only_live_unscored_assignments():
    previous = [row(1, 1, 10), row(2, 2, 10, "scored"), row(3, 3, 11), row(4, 4, 11)]
    existing = {(1, 10), (2, 10), (3, 11), (4, 11)}
    assert replaceable_pairs(previous, existing, stale_ids={4}) == {(1, 10), (3, 11)}


def test_split_plan_keeps_wanted_replaceable_pairs_and_drops_the_rest():
    replaceable = {(1, 10), (3, 11)}
    added, dropped = split_plan([(1, 10), (5, 12)], replaceable)
    assert added == [(5, 12)]
    assert dropped == [(3, 11)]


def test_fingerprint_changes_with_the_plan_the_round_version_and_the_mode():
    base = plan_fingerprint(ROUND, VALUES, {10, 11}, [(1, 10)], [])
    assert base == plan_fingerprint(ROUND, VALUES, {11, 10}, [(1, 10)], [])
    assert base != plan_fingerprint(ROUND, VALUES, {10, 11}, [(2, 10)], [])
    assert base != plan_fingerprint(SimpleNamespace(pk=7, version=4), VALUES, {10, 11}, [(1, 10)], [])
    assert base != plan_fingerprint(ROUND, {**VALUES, "existing": "replace"}, {10, 11}, [(1, 10)], [])


def test_stale_fingerprint_is_a_409_and_a_missing_one_is_allowed():
    require_fresh({}, "a" * 64)
    require_fresh({"plan_fingerprint": "a" * 64}, "a" * 64)
    with pytest.raises(ProgrammeError) as raised:
        require_fresh({"plan_fingerprint": "b" * 64}, "a" * 64)
    assert raised.value.status_code == 409
    assert raised.value.detail["code"] == "plan_changed"
