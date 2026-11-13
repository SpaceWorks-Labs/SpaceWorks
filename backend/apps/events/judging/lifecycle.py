"""B amendment hook and F/G recoverable notification-intent delivery seam."""

from django.utils.translation import gettext
from apps.operations.cloud_jobs import bounded
import logging

from django.http import Http404

from .boundary import assert_locked, audit, notice
from .ballot_invalidation import invalidate_pairwise_locked, invalidate_peers_locked
from .models_results import JudgingNotice
from .models_scoring import JudgeAssignment
from .ports import runtime

logger = logging.getLogger(__name__)


def invalidate_snapshot_locked(*, event, snapshot_id, locks, actor):
    """B invokes after supersession/disqualification in the same event transaction."""
    assert_locked(locks)
    snapshot = runtime().snapshot(snapshot_id)
    if snapshot.event_id != event.pk or event.pk != locks.event_id:
        raise Http404
    count = 0
    # Parent rounds precede assignments, matching score/close ordering.
    from .models_definitions import JudgingRound
    round_ids = JudgeAssignment.objects.filter(event=event, submission_snapshot_id=snapshot_id).values_list("round_id", flat=True)
    rounds = JudgingRound.objects.select_for_update().filter(event=event, pk__in=round_ids).order_by("pk")
    for round in rounds:
        for row in round.assignments.select_for_update().filter(submission_snapshot_id=snapshot_id).order_by("pk"):
            if row.state != "invalidated":
                if round.mode == "top3":
                    count += invalidate_peers_locked(event=event, actor=actor, assignment=row, locks=locks)
                elif round.mode == "pairwise":
                    count += invalidate_pairwise_locked(event=event, actor=actor, assignment=row, locks=locks,
                                                        reason=lambda: _snapshot_reason(event, actor))
                row.state = "invalidated"
                row.version += 1
                row.save(update_fields=("state", "version"))
                notice(event, "assignment_invalidated", row.pk, row.version)
                count += 1
    if count:
        audit(event, actor, "snapshot_judging_invalidated", event, snapshot_id=snapshot_id, count=count)
    # Immutable scores/results remain historical; live reads already refuse this snapshot.
    return count


def _snapshot_reason(event, actor):
    from .models_scoring import JudgingReason
    return JudgingReason.objects.create(event=event, makerspace_id=event.makerspace_id, actor=actor,
                                        body=gettext("The submission changed or is no longer eligible."))


def sweep_notices(*, after_id=None, limit=100):
    """F/G deduplicates by notice ID and rechecks released source + recipients on send.

    No lease or network call is held under an event transaction. Retrying a notice
    is intentional: the notification envelope/outbox owns durable dispatch claims.
    """
    from apps.events.tasks_sweeps import take_ids
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    from apps.makerspaces.scheduled_scope import live_space_ids
    live = JudgingNotice.objects.filter(event__makerspace_id__in=live_space_ids("events"))
    ids = (take_ids("judging-notices", live, limit=limit) if after_id is None else
           list(live.filter(pk__gt=after_id).order_by("pk").values_list("pk", flat=True)[:min(limit, 500)]))
    failed = 0
    counts = {"skipped": 0}
    for pk in bounded.items(ids):
        try:
            notice = JudgingNotice.objects.select_related("event").get(pk=pk)
            with fanout_tenant_write(notice.event.makerspace_id, operation="event_judging_notices", counts=counts) as allowed:
                if not allowed:
                    continue
                runtime().notify_intent(pk)
        except Exception:
            failed += 1
            logger.warning("event_judging_notice_retry_failed", extra={"notice_id": pk})
    return {"last_id": ids[-1] if ids else (after_id or 0), "count": len(ids), "failed": failed, **counts}
