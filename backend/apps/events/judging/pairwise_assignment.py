"""Choose the next project a pairwise judge sees. Pure and replayable: no ORM, seeded draws only.

Order: avoid projects another judge has in view (unless nothing else is left), then coverage
first (fewer than min_reviews valid comparisons), then the highest expected information gain
against the judge's previous project, then a sha256 tie-break. With probability `exploration`
the pick is uniform among the same top tier instead. Eligibility (conflicts, track/room scope,
already seen) is decided by the caller through the existing `conflicts.eligible`.
"""

from hashlib import sha256

from .pairwise_ranking import expected_information_gain


def draw(seed, round_id, judge_id, counter):
    """A deterministic uniform value in [0, 1) for the counter-th draw of this judge in this round."""
    digest = sha256(f"{seed}:{round_id}:{judge_id}:{counter}".encode()).hexdigest()
    return int(digest[:13], 16) / 16 ** 13


def tie_break(round_id, judge_id, snapshot_id):
    return sha256(f"{round_id}:{judge_id}:{snapshot_id}".encode()).hexdigest()


def choose(candidates, *, state, judge_id, previous, counts, min_reviews, in_view, round_id, counter):
    """Return (snapshot_id or None, next_counter). `counts` holds valid comparisons per project."""
    candidates = sorted(set(candidates), key=lambda pk: tie_break(round_id, judge_id, pk))
    if not candidates:
        return None, counter
    free = [pk for pk in candidates if pk not in in_view] or candidates
    tier = [pk for pk in free if counts.get(pk, 0) < min_reviews] or free
    seed = state.params.get("seed", str(round_id))
    explore, pick = draw(seed, round_id, judge_id, counter), draw(seed, round_id, judge_id, counter + 1)
    if explore < state.params["exploration"]:
        return tier[int(pick * len(tier))], counter + 2

    def gain(pk):
        if previous is None:
            return 0.0
        return round(expected_information_gain(state, judge_id, previous, pk), 12)

    # Highest gain wins; the hash order of `tier` breaks equal gains deterministically.
    best = max(enumerate(tier), key=lambda item: (gain(item[1]), -item[0]))[1]
    return best, counter + 2
