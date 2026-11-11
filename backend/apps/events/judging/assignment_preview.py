"""Parity E-B4 (D10): the assignment preview's per-judge loads, keep/replace split and plan fingerprint.

A preview (``dry_run``) and the apply that follows it must act on the same plan. The fingerprint is a
digest of the round version, the inputs and the pairs that would be added or dropped; an apply that
carries a preview's fingerprint is refused with 409 ``plan_changed`` when anything moved in between.
"""

from collections import Counter

from .boundary import digest
from .errors import ProgrammeError


def replaceable_pairs(previous, existing, stale_ids):
    """Live, unscored assignments a ``replace`` run may re-plan. Scored work is always kept."""
    return {(row.submission_snapshot_id, row.judge_role_assignment_id) for row in previous
            if row.state == "assigned" and row.pk not in stale_ids
            and (row.submission_snapshot_id, row.judge_role_assignment_id) in existing}


def split_plan(plan_pairs, replaceable):
    """(added, dropped): pairs to create, and replaceable pairs the new plan no longer wants."""
    wanted = set(plan_pairs)
    return [pair for pair in plan_pairs if pair not in replaceable], sorted(replaceable - wanted)


def loads_before(existing, judge_ids):
    counts = Counter(judge for _, judge in existing)
    return {str(judge): counts.get(judge, 0) for judge in sorted(judge_ids)}


def plan_fingerprint(round, values, judge_ids, added, dropped):
    return digest({"round": round.pk, "round_version": round.version, "strategy": values["strategy"],
                   "seed": values["seed"], "max_load": values["max_load"], "existing": values["existing"],
                   "judges": sorted(judge_ids), "added": sorted(added), "dropped": sorted(dropped)})


def require_fresh(values, fingerprint):
    sent = values.get("plan_fingerprint")
    if sent and sent != fingerprint:
        raise ProgrammeError("plan_changed", "The assignment plan changed since the preview; preview it again.")
