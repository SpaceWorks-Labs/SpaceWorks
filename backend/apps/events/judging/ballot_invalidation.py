"""A six-point ballot is indivisible when any of its exposed projects is invalidated."""

from .boundary import assert_locked, audit
from .models_scoring import JudgeAssignment, JudgeRankingBallot


def invalidate_peers_locked(*, event, actor, assignment, locks):
    assert_locked(locks)
    if not JudgeRankingBallot.objects.filter(round_id=assignment.round_id,
            judge_id=assignment.judge_role_assignment_id, batch=assignment.batch).exists():
        return 0
    peers = JudgeAssignment.objects.select_for_update().filter(round_id=assignment.round_id,
        judge_role_assignment_id=assignment.judge_role_assignment_id, batch=assignment.batch,
        state="scored").exclude(pk=assignment.pk).order_by("pk")
    count = 0
    for peer in peers:
        peer.state = "invalidated"
        peer.version += 1
        peer.save(update_fields=("state", "version"))
        count += 1
    if count:
        audit(event, actor, "ballot_exposure_invalidated", assignment, count=count, round_id=assignment.round_id)
    return count
