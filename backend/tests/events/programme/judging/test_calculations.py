from decimal import Decimal

import pytest

from apps.events.judging.calculations import (
    Ballot, Criterion, Judgment, estimate_judges, top3_points, top3_results, weighted_results, weighted_value,
)

CRITERIA = [Criterion("build", Decimal("2")), Criterion("impact", Decimal("1"))]


def test_decimal_weights_normalize_by_their_sum():
    assert weighted_value({"build": 5, "impact": 2}, CRITERIA) == Decimal(4)


@pytest.mark.parametrize("value", [True, False, 0, 6, 2.5, "3", None])
def test_score_values_are_strict_integers(value):
    with pytest.raises(ValueError):
        weighted_value({"build": value, "impact": 3}, CRITERIA)


@pytest.mark.parametrize("values", [{"build": 3}, {"build": 3, "impact": 3, "unknown": 4}])
def test_frozen_criterion_keys_are_exact(values):
    with pytest.raises(ValueError):
        weighted_value(values, CRITERIA)


@pytest.mark.parametrize("weight", ["0", "-1", "NaN", "Infinity"])
def test_nonpositive_or_nonfinite_weights_refuse(weight):
    with pytest.raises(ValueError):
        weighted_value({"build": 3}, [Criterion("build", Decimal(weight))])


def test_missing_reviews_do_not_become_zero_and_ties_keep_the_same_rank():
    reviews = [Judgment(snapshot, judge, {"build": 4, "impact": 4}) for snapshot in (11, 12) for judge in (1, 2, 3)]
    rows = weighted_results([12, 13, 11], reviews, CRITERIA)
    assert [(row["snapshot_id"], row["rank"]) for row in rows] == [(11, 1), (12, 1), (13, 3)]
    missing = rows[-1]
    assert missing["score"] is None and missing["n"] == 0 and not missing["coverage_complete"]
    assert rows[0]["score"] == "4.00000000" and rows[0]["n"] == 3


def test_ties_use_frozen_criterion_priority_without_an_id_tiebreak():
    criteria = [Criterion("build", Decimal(1)), Criterion("impact", Decimal(1))]
    rows = weighted_results([100, 1], [Judgment(100, 9, {"build": 5, "impact": 1}),
        Judgment(1, 10, {"build": 1, "impact": 5})], criteria)
    assert rows[0]["snapshot_id"] == 100 and rows[0]["rank"] == 1


def test_zero_variance_zscores_are_zero_and_low_n_is_visible():
    rows = weighted_results([11, 12], [Judgment(s, 9, {"build": 3, "impact": 3}) for s in (11, 12)],
                             CRITERIA, normalization="zscore")
    assert all(row["zscore"] == "0.00000000" for row in rows)
    assert all({"zero_judge_variance", "low_judge_n"} <= set(row["warnings"]) for row in rows)


def test_duplicate_same_member_judgments_are_refused():
    judgment = Judgment(11, 9, {"build": 4, "impact": 4})
    with pytest.raises(ValueError):
        weighted_results([11], [judgment, judgment], CRITERIA)


@pytest.mark.parametrize("exposed,ranked,expected", [
    ((11,), (11,), {11: Decimal(6)}),
    ((11, 12), (11, 12), {11: Decimal("3.6"), 12: Decimal("2.4")}),
    ((11, 12, 13, 14), (13, 12, 11), {13: Decimal(3), 12: Decimal(2), 11: Decimal(1)}),
])
def test_every_ballot_uses_a_six_point_budget(exposed, ranked, expected):
    points = top3_points(exposed, ranked)
    assert points == expected and sum(points.values()) == 6


@pytest.mark.parametrize("ranked", [(11, 11, 12), (11, 12), (11, 12, 99), (11, 12, 13, 14)])
def test_rankings_refuse_duplicates_missing_slots_and_unassigned_ids(ranked):
    with pytest.raises(ValueError):
        top3_points((11, 12, 13, 14), ranked)


def test_unranked_submitted_views_count_as_exposure_but_missing_ballots_do_not():
    rows = top3_results([11, 12, 13, 14], [Ballot(j, "one", (11, 12, 13, 14), (11, 12, 13)) for j in (1, 2, 3)])
    assert rows[-1]["snapshot_id"] == 14 and rows[-1]["score"] == "0.00000000" and rows[-1]["n"] == 3
    assert all(row["coverage_complete"] for row in rows)


def test_unequal_exposure_is_explicit_and_blocks_coverage():
    rows = top3_results([11, 12], [Ballot(1, "one", (11, 12), (11, 12)), Ballot(2, "two", (11,), (11,))])
    assert all("unequal_exposure" in row["warnings"] and not row["coverage_complete"] for row in rows)


def test_judge_estimate_rounds_up():
    assert estimate_judges(31, 3, 4, 45) == 9
    assert estimate_judges(0, 3, 4, 45) == 0
    with pytest.raises(ValueError):
        estimate_judges(10, 3, 4, 0)
