"""Pure, versioned judging arithmetic. Decimal output is JSON-safe and reproducible."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, localcontext
from math import ceil

ALGORITHM_VERSION = "spaceworks-judging-v1"
ZERO = Decimal(0)


@dataclass(frozen=True)
class Criterion:
    key: str
    weight: Decimal


@dataclass(frozen=True)
class Judgment:
    snapshot_id: int
    judge_id: int
    values: dict


@dataclass(frozen=True)
class Ballot:
    judge_id: int
    batch: str
    exposed: tuple[int, ...]
    ordered_top3: tuple[int, ...]


def decimal_text(value):
    return format(value.quantize(Decimal("0.00000001")), "f")


def validate_criteria(criteria):
    if not criteria or len(criteria) > 30 or len({c.key for c in criteria}) != len(criteria):
        raise ValueError("Use 1–30 distinct criteria.")
    for criterion in criteria:
        if not criterion.key or not criterion.weight.is_finite() or criterion.weight <= ZERO:
            raise ValueError("Criterion weights must be finite and positive.")


def weighted_value(values, criteria):
    validate_criteria(criteria)
    if set(values) != {c.key for c in criteria}:
        raise ValueError("Provide exactly the frozen criterion keys.")
    if any(type(value) is not int or not 1 <= value <= 5 for value in values.values()):
        raise ValueError("Each score must be an integer from 1 to 5.")
    return sum((c.weight * values[c.key] for c in criteria), ZERO) / sum(c.weight for c in criteria)


def _rank(rows):
    # Snapshot ID stabilizes display order only; identical vectors KEEP a tied rank.
    rows.sort(key=lambda row: row["_vector"], reverse=True)
    previous = None
    rank = 0
    for index, row in enumerate(rows, start=1):
        vector = row.pop("_vector")
        if vector != previous:
            rank = index
        row["rank"] = rank
        previous = vector
    return rows


def weighted_results(snapshot_ids, judgments, criteria, *, min_reviews=3, normalization="none"):
    validate_criteria(criteria)
    if normalization not in ("none", "zscore"):
        raise ValueError("Unknown normalization.")
    ids = sorted(set(snapshot_ids))
    by_project, by_judge, seen = defaultdict(list), defaultdict(list), set()
    with localcontext() as context:
        context.prec = 36
        for judgment in judgments:
            pair = (judgment.snapshot_id, judgment.judge_id)
            if pair in seen or judgment.snapshot_id not in ids:
                raise ValueError("Duplicate or foreign judgment.")
            seen.add(pair)
            score = weighted_value(judgment.values, criteria)
            by_project[judgment.snapshot_id].append((judgment, score))
            by_judge[judgment.judge_id].append(score)
        moments = {}
        for judge, scores in by_judge.items():
            mean = sum(scores, ZERO) / len(scores)
            variance = sum(((score - mean) ** 2 for score in scores), ZERO) / len(scores)
            moments[judge] = (mean, variance.sqrt(), len(scores))
        rows = []
        for snapshot_id in ids:
            items = by_project[snapshot_id]
            n = len(items)
            raw = sum((score for _, score in items), ZERO) / n if n else None
            averages = {c.key: sum((Decimal(j.values[c.key]) for j, _ in items), ZERO) / n
                        for c in criteria} if n else {}
            diagnostics, warnings = [], []
            for judgment, score in items:
                mean, deviation, count = moments[judgment.judge_id]
                diagnostics.append((score - mean) / deviation if deviation else ZERO)
                if count < 3:
                    warnings.append("low_judge_n")
                if not deviation:
                    warnings.append("zero_judge_variance")
            normalized = sum(diagnostics, ZERO) / n if n else None
            selected = normalized if normalization == "zscore" else raw
            # Missing judgments remain null and never contribute an invented zero.
            rows.append({"snapshot_id": snapshot_id, "n": n, "coverage_complete": n >= min_reviews,
                         "score": decimal_text(selected) if selected is not None else None,
                         "raw_score": decimal_text(raw) if raw is not None else None,
                         "zscore": decimal_text(normalized) if normalized is not None else None,
                         "criterion_averages": {k: decimal_text(v) for k, v in averages.items()},
                         "distribution": dict(sorted(Counter(decimal_text(score) for _, score in items).items())),
                         "warnings": sorted(set(warnings + (["insufficient_reviews"] if n < min_reviews else []))),
                         "_vector": (selected is not None, selected or ZERO,
                                     *(averages.get(c.key, ZERO) for c in criteria))})
        return _rank(rows)


def top3_points(exposed, ranked):
    if not exposed or len(set(exposed)) != len(exposed):
        raise ValueError("Use distinct assigned projects.")
    if len(ranked) != min(3, len(exposed)) or len(set(ranked)) != len(ranked) or not set(ranked) <= set(exposed):
        raise ValueError("Rank exactly the top three distinct assigned projects, or the entire smaller batch.")
    budget = sum((Decimal(3 - index) for index in range(len(ranked))), ZERO)
    return {snapshot: Decimal(3 - index) * 6 / budget for index, snapshot in enumerate(ranked)}


def top3_results(snapshot_ids, ballots, *, min_reviews=3):
    ids, points, counts, seen = sorted(set(snapshot_ids)), defaultdict(lambda: ZERO), Counter(), set()
    for ballot in ballots:
        identity = (ballot.judge_id, ballot.batch)
        if identity in seen or not set(ballot.exposed) <= set(ids):
            raise ValueError("Duplicate ballot or foreign project.")
        seen.add(identity)
        allocated = top3_points(ballot.exposed, ballot.ordered_top3)
        for snapshot in ballot.exposed:
            counts[snapshot] += 1  # A submitted unranked view counts as exposure, with zero ranking points.
            points[snapshot] += allocated.get(snapshot, ZERO)
    unequal = len({counts[snapshot] for snapshot in ids}) > 1
    return _rank([{"snapshot_id": snapshot, "n": counts[snapshot],
                   "coverage_complete": counts[snapshot] >= min_reviews and not unequal,
                   "score": decimal_text(points[snapshot]) if counts[snapshot] else None,
                   "warnings": (["unequal_exposure"] if unequal else [])
                   + (["insufficient_reviews"] if counts[snapshot] < min_reviews else []),
                   "_vector": (counts[snapshot] > 0, points[snapshot])} for snapshot in ids])


def estimate_judges(projects, target_views, minutes_per_view, judging_minutes):
    if any(type(value) is not int or value <= 0 for value in (target_views, minutes_per_view, judging_minutes)):
        raise ValueError("Use positive integer timing and coverage values.")
    if type(projects) is not int or projects < 0:
        raise ValueError("Use a nonnegative project count.")
    return ceil(projects * target_views * minutes_per_view / judging_minutes)
