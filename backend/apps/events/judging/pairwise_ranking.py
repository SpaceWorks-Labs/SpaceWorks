"""Crowd Bradley–Terry (CrowdBT) pairwise ranking, written from the published paper.

Chen, Bennett, Collins-Thompson and Horvitz, "Pairwise Ranking Aggregation in a Crowdsourced
Setting" (WSDM 2013). Each project has a Gaussian quality N(mu, sigma2); each judge has a
Beta(alpha, beta) reliability. One observation "winner beat loser" applies the paper's
closed-form moment-matching update. Pure Python and deterministic: no ORM, no randomness.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from math import exp, lgamma, log, sqrt

PAIRWISE_VERSION = "spaceworks-pairwise-crowdbt-v1"
DEFAULTS = {"mu": 0.0, "sigma2": 1.0, "alpha": 10.0, "beta": 1.0, "gamma": 0.1, "kappa": 0.0001,
            "exploration": 0.1, "low_confidence_sigma": 0.85}


@dataclass(frozen=True)
class Comparison:
    judge_id: int
    winner: int
    loser: int


@dataclass
class State:
    params: dict
    projects: dict = field(default_factory=dict)  # snapshot id -> (mu, sigma2)
    judges: dict = field(default_factory=dict)  # judge id -> (alpha, beta)

    def project(self, pk):
        return self.projects.get(pk, (self.params["mu"], self.params["sigma2"]))

    def judge(self, pk):
        return self.judges.get(pk, (self.params["alpha"], self.params["beta"]))


def digamma(x):
    """psi(x) for x > 0: upward recurrence, then the asymptotic series."""
    if x <= 0:
        raise ValueError("digamma is defined here for positive values only.")
    result = 0.0
    while x < 10:  # the asymptotic tail is then accurate to about 1e-13
        result -= 1 / x
        x += 1
    inverse = 1 / (x * x)
    return result + log(x) - 0.5 / x - inverse * (1 / 12 - inverse * (1 / 120 - inverse * (1 / 252 - inverse / 240)))


def _log_beta(a, b):
    return lgamma(a) + lgamma(b) - lgamma(a + b)


def _posterior(state, judge_id, winner, loser):
    """The paper's update for one observation; returns new (winner, loser, judge) parameters."""
    (mu_w, s_w), (mu_l, s_l) = state.project(winner), state.project(loser)
    alpha, beta = state.judge(judge_id)
    p = 1 / (1 + exp(mu_l - mu_w))  # Bradley–Terry probability that the winner is better
    # The paper's second-order estimate of E[p] under both Gaussians (its C1; C2 = 1 - C1).
    c1 = p + 0.5 * (s_w + s_l) * p * (1 - p) * (1 - 2 * p)
    expected = (alpha * c1 + beta * (1 - c1)) / (alpha + beta)  # C: probability of this observation
    a = alpha * p / (alpha * p + beta * (1 - p))
    gradient, curvature = a - p, a * (1 - a) - p * (1 - p)
    kappa = state.params["kappa"]
    new_w = (mu_w + s_w * gradient, s_w * max(1 + s_w * curvature, kappa))
    new_l = (mu_l - s_l * gradient, s_l * max(1 + s_l * curvature, kappa))
    total = alpha + beta
    first = (c1 * alpha * (alpha + 1) + (1 - c1) * alpha * beta) / (total * (total + 1) * expected)
    second = (c1 * alpha * (alpha + 1) * (alpha + 2) + (1 - c1) * alpha * (alpha + 1) * beta) / (
        total * (total + 1) * (total + 2) * expected)
    spread = second - first * first
    new_judge = ((first - second) * first / spread, (first - second) * (1 - first) / spread)
    return new_w, new_l, new_judge, expected


def update(state, comparison):
    new_w, new_l, new_judge, _ = _posterior(state, comparison.judge_id, comparison.winner, comparison.loser)
    state.projects[comparison.winner], state.projects[comparison.loser] = new_w, new_l
    state.judges[comparison.judge_id] = new_judge
    return state


def _kl_normal(new, old):
    (m1, v1), (m0, v0) = new, old
    return 0.5 * (log(v0 / v1) + (v1 + (m1 - m0) ** 2) / v0 - 1)


def _kl_beta(new, old):
    (a1, b1), (a0, b0) = new, old
    return (_log_beta(a0, b0) - _log_beta(a1, b1) + (a1 - a0) * digamma(a1) + (b1 - b0) * digamma(b1)
            + (a0 - a1 + b0 - b1) * digamma(a1 + b1))


def expected_information_gain(state, judge_id, first, second):
    """Expected KL(posterior || prior) over both outcomes; the judge term is weighted by gamma."""
    total = 0.0
    for winner, loser in ((first, second), (second, first)):
        new_w, new_l, new_judge, probability = _posterior(state, judge_id, winner, loser)
        gain = (_kl_normal(new_w, state.project(winner)) + _kl_normal(new_l, state.project(loser))
                + state.params["gamma"] * _kl_beta(new_judge, state.judge(judge_id)))
        total += probability * gain
    return total


def replay(comparisons, params):
    """Apply decisive comparisons in their recorded order; the input is already filtered to valid rows."""
    state = State({**DEFAULTS, **params})
    for comparison in comparisons:
        update(state, comparison)
    return state


def _text(value):
    return format(Decimal(round(value, 4) + 0.0).quantize(Decimal("0.0001")), "f")


def pairwise_results(snapshot_ids, comparisons, params, *, min_reviews=3):
    """Rank by mu descending; equal mu to four decimals is a shared rank (routed to the tie decision)."""
    state = replay(comparisons, params)
    counts = {}
    for comparison in comparisons:
        for pk in (comparison.winner, comparison.loser):
            counts[pk] = counts.get(pk, 0) + 1
    threshold = state.params["low_confidence_sigma"]
    rows = []
    for pk in sorted(set(snapshot_ids)):
        n = counts.get(pk, 0)
        mu, sigma2 = state.project(pk)
        sigma = sqrt(sigma2)
        warnings = (["insufficient_reviews"] if n < min_reviews else []) + (
            ["low_confidence"] if n < min_reviews or sigma > threshold else [])
        rows.append({"snapshot_id": pk, "n": n, "coverage_complete": n >= min_reviews,
                     "score": _text(mu) if n else None, "sigma": _text(sigma), "warnings": warnings,
                     "_vector": (n > 0, Decimal(_text(mu)) if n else Decimal(0))})
    rows.sort(key=lambda row: row["_vector"], reverse=True)
    rank, previous = 0, None
    for index, row in enumerate(rows, start=1):
        vector = row.pop("_vector")
        if vector != previous:
            rank = index
        row["rank"], previous = rank, vector
    return rows
