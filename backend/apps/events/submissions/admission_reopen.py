"""A reopens membership through B while preserving immutable submitted history."""
from django.shortcuts import get_object_or_404
from apps.accounts.models import User
from apps.audit.services import record
from apps.events.models import Event
from apps.events.programme_locks import assert_lock_context
from .models_projects import HackathonSubmission
from .errors import SubmissionError


def has_submission(*, team_id, event_id):
    return HackathonSubmission.objects.filter(team_id=team_id, event_id=event_id,
        current_snapshot_id__isnull=False).exists()


def reopen_submission_locked(*, team_id, event_id, actor_id, reason, locks):
    assert_lock_context(locks)
    if locks.event_id != event_id or not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise SubmissionError("invalid_reopen")
    row = HackathonSubmission.objects.select_for_update().filter(team_id=team_id, event_id=event_id).first()
    if row is None or not row.current_snapshot_id:
        return None
    from apps.events.judging.lifecycle import invalidate_snapshot_locked
    event = get_object_or_404(Event, pk=event_id)
    actor = get_object_or_404(User, pk=actor_id)
    invalidate_snapshot_locked(event=event, snapshot_id=row.current_snapshot_id, locks=locks, actor=actor)
    # Historical snapshot IDs remain reachable only through history permissions;
    # no stale result/gallery can keep treating the previous seal as current.
    row.current_snapshot_id = None
    row.state, row.locked_at, row.triage = "draft", None, "pending"
    row.version += 1
    row.save(update_fields=("current_snapshot", "state", "locked_at", "triage", "version"))
    record(actor, "event.submission_review_transition", makerspace=event.makerspace, target=row,
        meta={"state": "draft", "reason_code": "roster_reopened", "version": row.version})
    return row.pk
