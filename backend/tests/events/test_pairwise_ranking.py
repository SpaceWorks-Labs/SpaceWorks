"""CrowdBT (Chen et al., WSDM 2013) against an independent exp-form transcription of the paper."""

from math import exp, isclose, sqrt

import pytest

from apps.events.judging.pairwise_assignment import choose, draw
from apps.events.judging.pairwise_ranking import (
    DEFAULTS, Comparison, State, digamma, expected_information_gain, pairwise_results, replay, update,
)


def paper_update(alpha, beta, mu_w, s_w, mu_l, s_l, kappa=1e-4):
    """The paper's equations written with exponentials, as printed (not the p-form in the module)."""
    ew, el = exp(mu_w), exp(mu_l)
    mult = alpha * ew / (alpha * ew + beta * el) - ew / (ew + el)
    curv = alpha * ew * beta * el / (alpha * ew + beta * el) ** 2 - ew * el / (ew + el) ** 2
    c1 = ew / (ew + el) + 0.5 * (s_w + s_l) * ew * el * (el - ew) / (ew + el) ** 3
    c2 = 1 - c1
    c = (c1 * alpha + c2 * beta) / (alpha + beta)
    e1 = (c1 * (alpha + 1) * alpha + c2 * alpha * beta) / (c * (alpha + beta + 1) * (alpha + beta))
    e2 = (c1 * (alpha + 2) * (alpha + 1) * alpha + c2 * (alpha + 1) * alpha * beta) / (
        c * (alpha + beta + 2) * (alpha + beta + 1) * (alpha + beta))
    var = e2 - e1 ** 2
    return ((mu_w + s_w * mult, s_w * max(1 + s_w * curv, kappa)), (mu_l - s_l * mult, s_l * max(1 + s_l * curv, kappa)),
            ((e1 - e2) * e1 / var, (e1 - e2) * (1 - e1) / var))


def test_first_comparison_from_the_priors_matches_the_hand_computed_fixture():
    state = update(State(dict(DEFAULTS)), Comparison(judge_id=1, winner=10, loser=20))
    # p = 0.5 and a = 10/11, so the gradient is 10/11 - 1/2 and the variance shrinks by 1 - 0.1673554.
    assert isclose(state.project(10)[0], 9 / 22, rel_tol=1e-12)
    assert isclose(state.project(20)[0], -9 / 22, rel_tol=1e-12)
    assert isclose(state.project(10)[1], 1 + (10 / 121 - 0.25), rel_tol=1e-12)
    # An even prior match tells nothing about the judge: Beta(10, 1) is unchanged.
    assert all(isclose(a, b, rel_tol=1e-9) for a, b in zip(state.judge(1), (10.0, 1.0)))


@pytest.mark.parametrize("mu_w,s_w,mu_l,s_l,alpha,beta", [
    (0.4, 0.8, -0.3, 0.9, 10.0, 1.0), (-1.2, 0.5, 0.7, 0.6, 6.0, 3.0), (2.0, 0.2, 1.9, 1.0, 12.5, 0.8)])
def test_every_update_matches_the_paper_equations(mu_w, s_w, mu_l, s_l, alpha, beta):
    state = State(dict(DEFAULTS), projects={1: (mu_w, s_w), 2: (mu_l, s_l)}, judges={7: (alpha, beta)})
    update(state, Comparison(7, 1, 2))
    winner, loser, judge = paper_update(alpha, beta, mu_w, s_w, mu_l, s_l)
    for got, want in ((state.project(1), winner), (state.project(2), loser), (state.judge(7), judge)):
        assert all(isclose(a, b, rel_tol=1e-9, abs_tol=1e-12) for a, b in zip(got, want))


def test_digamma_matches_known_values():
    assert isclose(digamma(1), -0.5772156649015329, rel_tol=1e-10)
    assert isclose(digamma(0.5), -1.9635100260214235, rel_tol=1e-10)
    assert isclose(digamma(10), 2.251752589066721, rel_tol=1e-10)


def test_replay_is_deterministic_and_order_matters_only_by_recorded_sequence():
    rows = [Comparison(1, 10, 20), Comparison(2, 20, 30), Comparison(1, 10, 30), Comparison(3, 30, 20)]
    first, second = replay(rows, {}), replay(list(rows), {})
    assert first.projects == second.projects and first.judges == second.judges
    assert pairwise_results([10, 20, 30], rows, {}) == pairwise_results([30, 20, 10], rows, {})


def test_results_rank_by_mu_share_equal_ranks_and_flag_low_coverage():
    rows = [Comparison(1, 10, 20), Comparison(2, 30, 40)]  # Two symmetric, disjoint wins.
    result = pairwise_results([10, 20, 30, 40, 50], rows, {}, min_reviews=3)
    by_id = {row["snapshot_id"]: row for row in result}
    assert by_id[10]["rank"] == by_id[30]["rank"] == 1  # equal mu to four decimals: a shared rank
    assert by_id[20]["rank"] == by_id[40]["rank"] == 3
    assert by_id[50]["n"] == 0 and by_id[50]["score"] is None and by_id[50]["rank"] == 5
    assert all("insufficient_reviews" in row["warnings"] and not row["coverage_complete"] for row in result)


def test_three_comparisons_reach_coverage_and_a_consistent_winner_ranks_first():
    rows = [Comparison(j, 1, 2) for j in (1, 2, 3)] + [Comparison(j, 2, 3) for j in (1, 2, 3)] + [
        Comparison(j, 1, 3) for j in (1, 2, 3)]
    result = pairwise_results([1, 2, 3], rows, {}, min_reviews=3)
    assert [row["snapshot_id"] for row in result] == [1, 2, 3]
    assert all(row["coverage_complete"] and row["n"] == 6 for row in result)
    assert float(result[0]["sigma"]) < 1 and isclose(float(result[0]["sigma"]) ** 2,
                                                      replay(rows, {}).project(1)[1], abs_tol=1e-3)


def test_information_gain_prefers_the_uncertain_project_and_is_nonnegative():
    state = State(dict(DEFAULTS), projects={1: (0.0, 0.2), 2: (0.0, 1.0), 3: (0.0, 0.2)})
    assert expected_information_gain(state, 9, 1, 2) > expected_information_gain(state, 9, 1, 3) >= 0


def test_selection_is_coverage_first_then_information_gain_and_replayable():
    state = State({**DEFAULTS, "exploration": 0.0, "seed": "round-1"}, projects={2: (0.0, 1.0), 3: (0.0, 0.1)})
    common = dict(state=state, judge_id=5, previous=1, min_reviews=3, in_view=set(), round_id=1, counter=0)
    # Project 3 still needs coverage, so it wins although project 2 carries more information.
    assert choose([2, 3], counts={2: 3, 3: 1}, **common)[0] == 3
    assert choose([2, 3], counts={2: 3, 3: 3}, **common)[0] == 2
    # Projects in another judge's view are avoided unless nothing else is left.
    assert choose([2, 3], counts={}, **{**common, "in_view": {2}})[0] == 3
    assert choose([2], counts={}, **{**common, "in_view": {2}})[0] == 2
    assert choose([], counts={}, **common) == (None, 0)
    assert draw("s", 1, 5, 0) == draw("s", 1, 5, 0) and 0 <= draw("s", 1, 5, 0) < 1


def test_exploration_draws_are_seeded_so_a_replay_gives_the_same_sequence():
    state = State({**DEFAULTS, "exploration": 1.0, "seed": "round-9"})
    picks = [choose(range(1, 9), state=state, judge_id=4, previous=None, counts={}, min_reviews=3,
                    in_view=set(), round_id=9, counter=step * 2) for step in range(6)]
    again = [choose(range(1, 9), state=state, judge_id=4, previous=None, counts={}, min_reviews=3,
                    in_view=set(), round_id=9, counter=step * 2) for step in range(6)]
    assert picks == again and len({pick for pick, _ in picks}) > 1
    assert sqrt(DEFAULTS["sigma2"]) == 1.0
