"""#180 S15: reminders to judges with unfinished assignments, behind a per-round switch (off).

Three per open round: when it opens, at its midpoint (with a window) and 24 hours before it closes.
Each is one judging notice (source = the round, revision = 1/2/3), so a reminder is never sent twice;
recipients are recomputed at delivery (judges who still have assigned, unscored work).
"""
import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)
OPENED, MIDPOINT, CLOSING = 1, 2, 3


def phases_due(round, now):
    due = [OPENED]
    if round.opens_at and round.closes_at and now >= round.opens_at + (round.closes_at - round.opens_at) / 2:
        due.append(MIDPOINT)
    if round.closes_at and round.closes_at - timedelta(hours=24) <= now < round.closes_at:
        due.append(CLOSING)
    return due


def remind_judges(now=None, limit=100):
    from apps.events.judging.boundary import notice
    from apps.events.judging.models_definitions import JudgingRound
    from .ports import boundary
    now = now or timezone.now()
    queued = 0
    for round in JudgingRound.objects.filter(judge_reminders=True, state="open").order_by("pk")[:limit]:
        if round.closes_at and now >= round.closes_at:
            continue
        try:
            with boundary().locked(actor=None, event_id=round.event_id, team_id=None, action="stage_reminder") as ctx:
                for phase in phases_due(round, now):
                    notice(ctx.event, "judge_reminder", round.pk, phase)
                    queued += 1
        except Exception:
            logger.warning("event_judge_reminder_deferred", extra={"round_id": round.pk})
    return queued


def recipients(row):
    from apps.events.judging.models_definitions import JudgingRound
    from apps.events.judging.models_scoring import JudgeAssignment
    from apps.events.judging.ports import runtime
    round = JudgingRound.objects.filter(pk=row.source_id, event_id=row.event_id).first()
    if round is None or round.state != "open" or not round.judge_reminders:
        return ()
    members = set()
    for judge_id in (JudgeAssignment.objects.filter(round=round, state="assigned")
                     .values_list("judge_role_assignment_id", flat=True).distinct()):
        judge = runtime().judge(judge_id)
        if judge.active and judge.event_id == row.event_id:
            members.add(judge.member_id)
    return tuple(sorted(members))
