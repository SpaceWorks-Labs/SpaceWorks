from collections import Counter
from itertools import product

import pytest

from apps.events.judging.assignment_planner import plan_assignments


def test_balanced_deterministic_distinct_nonconflicted_views():
    blocked = {(1, 10), (2, 11), (3, 12)}
    first = plan_assignments([1, 2, 3, 4], [10, 11, 12, 13], blocked=blocked, seed="event-42")
    again = plan_assignments([4, 2, 1, 3], [13, 11, 10, 12], blocked=blocked, seed="event-42")
    assert first == again and not first.deficits
    assert len(first.pairs) == len(set(first.pairs)) == 12
    assert not set(first.pairs) & blocked
    assert set(Counter(p for p, _ in first.pairs).values()) == {3}
    assert max(first.loads.values()) - min(first.loads.values()) <= 1


def test_capacity_shortage_is_not_claimed_as_complete():
    plan = plan_assignments([1, 2], [10, 11, 12], max_load=1)
    assert sum(plan.deficits.values()) == 3
    assert max(plan.loads.values()) == 1


def test_existing_assignments_count_without_being_assigned_twice():
    existing = {(1, 10), (1, 11), (1, 12)}
    plan = plan_assignments([1, 2], [10, 11, 12], existing=existing)
    assert not plan.deficits and not set(plan.pairs) & existing
    assert {p for p, _ in plan.pairs} == {2}


def test_augmenting_paths_satisfy_restricted_projects_without_a_greedy_false_shortage():
    # Last project can use only 10/11/12. All judges have capacity two.
    blocked = {(3, 13)}
    plan = plan_assignments([1, 2, 3], [10, 11, 12, 13, 14], blocked=blocked | {(3, 14)}, max_load=2)
    assert not plan.deficits
    assert {j for p, j in plan.pairs if p == 3} == {10, 11, 12}


@pytest.mark.parametrize("mask", range(16))
def test_small_graph_cardinality_matches_exhaustive_feasibility(mask):
    # Two projects each already have two views. One additional slot per project,
    # two remaining judge slots; enumerate every allowed-edge graph.
    existing = {(1, 20), (1, 21), (2, 20), (2, 21)}
    candidates = [(1, 10), (1, 11), (2, 10), (2, 11)]
    blocked = {pair for i, pair in enumerate(candidates) if mask & (1 << i)}
    blocked |= {(p, j) for p in (1, 2) for j in (20, 21)}
    plan = plan_assignments([1, 2], [10, 11, 20, 21], existing=existing, blocked=blocked, max_load=2)
    feasible = any((1, a) not in blocked and (2, b) not in blocked for a, b in product((10, 11), repeat=2))
    assert (not plan.deficits) == feasible


@pytest.mark.parametrize("options", [{"target_views": 2}, {"max_load": 0}, {"max_load": True}])
def test_invalid_limits_fail_at_the_boundary(options):
    with pytest.raises(ValueError):
        plan_assignments([1], [10, 11, 12], **options)
