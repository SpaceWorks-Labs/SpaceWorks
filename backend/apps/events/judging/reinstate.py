"""Parity E-B4 (D7): give a reinstated project its judging work back.

Disqualifying invalidates the project's live assignments (`lifecycle.invalidate_snapshot_locked`); the
submitted scores and ballots are immutable and were never deleted. Reinstating flips each invalidated
assignment back to `scored` (a submitted score or ranking exists) or `assigned`, but only when its judge
is still eligible, so a conflict raised in the meantime is never undone. Rounds that already finalized
keep their frozen evidence, and pairwise comparisons are append-only invalidations, so both are left as
they are and counted as skipped.
"""

from django.http import Http404

from .boundary import assert_locked, audit, notice
from .conflicts import eligible
from .models_definitions import JudgingRound
from .models_scoring import JudgeAssignment, JudgeRankingChoice, JudgeScore
from .ports import runtime


def _was_scored(round, row):
    if round.mode == "top3":
        return JudgeRankingChoice.objects.filter(assignment=row).exists()
    return JudgeScore.objects.filter(assignment=row, submitted_at__isnull=False).exists()


def _restore(event, actor, round, row):
    """Restore one invalidated assignment if its judge may still judge it. Returns True when restored."""
    judge = runtime().judge(row.judge_role_assignment_id)
    snapshot = runtime().snapshot(row.submission_snapshot_id)
    if not eligible(judge, snapshot, round):
        return False
    row.state = "scored" if _was_scored(round, row) else "assigned"
    row.version += 1
    row.save(update_fields=("state", "version"))
    if row.state == "assigned":
        notice(event, "judge_assigned", row.pk, row.version)
    return True


def reinstate_snapshot_locked(*, event, snapshot_id, locks, actor):
    """Run in the reinstating transaction, after the project's triage is eligible again."""
    assert_locked(locks)
    snapshot = runtime().snapshot(snapshot_id)
    if snapshot.event_id != event.pk or event.pk != locks.event_id:
        raise Http404
    round_ids = JudgeAssignment.objects.filter(event=event, submission_snapshot_id=snapshot_id,
                                               state="invalidated").values_list("round_id", flat=True)
    restored = skipped = 0
    for round in JudgingRound.objects.select_for_update().filter(event=event, pk__in=set(round_ids)).order_by("pk"):
        rows = list(round.assignments.select_for_update().filter(
            submission_snapshot_id=snapshot_id, state="invalidated").order_by("pk"))
        if round.mode == "pairwise" or round.state == "finalized":
            skipped += len(rows)
            continue
        for row in rows:
            if not _restore(event, actor, round, row):
                skipped += 1
                continue
            restored += 1
            if round.mode != "top3":
                continue
            # A six-point ballot is indivisible: the peers dropped with this project come back with it.
            for peer in round.assignments.select_for_update().filter(
                    judge_role_assignment_id=row.judge_role_assignment_id, batch=row.batch,
                    state="invalidated").exclude(pk=row.pk).order_by("pk"):
                restored += int(_restore(event, actor, round, peer))
    if restored or skipped:
        audit(event, actor, "snapshot_judging_restored", event, snapshot_id=snapshot_id, count=restored)
    return {"restored": restored, "skipped": skipped}
