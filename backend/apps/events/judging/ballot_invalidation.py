"""A six-point ballot is indivisible when any of its exposed projects is invalidated; pairwise
comparisons that show an invalidated project are invalidated one by one (never reweighted)."""

from .boundary import assert_locked, audit, notice
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
        notice(event, "assignment_invalidated", peer.pk, peer.version)
        count += 1
    if count:
        audit(event, actor, "ballot_exposure_invalidated", assignment, count=count, round_id=assignment.round_id)
    return count


def invalidate_pairwise_locked(*, event, actor, assignment, reason, locks):
    """Pairwise: every still-valid comparison that shows this assignment gets an append-only invalidation."""
    from django.db.models import Q
    from .models_pairwise import JudgePairwiseComparison, JudgePairwiseInvalidation
    assert_locked(locks)
    rows = (JudgePairwiseComparison.objects.filter(round_id=assignment.round_id, invalidation__isnull=True)
            .filter(Q(previous_id=assignment.pk) | Q(current_id=assignment.pk)).order_by("sequence"))
    count = 0
    for row in rows:
        reason = reason() if callable(reason) else reason  # A factory creates the reason only when needed.
        JudgePairwiseInvalidation.objects.create(comparison=row, reason=reason)
        audit(event, actor, "pairwise_invalidated", row, round_id=row.round_id, sequence=row.sequence)
        count += 1
    return count
