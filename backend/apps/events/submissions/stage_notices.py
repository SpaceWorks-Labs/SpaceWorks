"""Stage notices (#178, #179): deadline reminders and shortlist results, on the judging notice source.

Both are per-event switches that start OFF (C-37): ``stage_reminder_email`` and ``shortlist_email``.
Recipients are recomputed live when each notice is delivered, so a team that submitted meanwhile, or
a member who left, is not told.
"""
from django.utils.translation import gettext
import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)
REMINDER_WINDOW = timedelta(hours=24)


def recipients(row):
    from .stage_shortlists import recipients as shortlist_recipients
    if row.kind in ("stage_shortlisted", "stage_not_shortlisted"):
        return shortlist_recipients(row.kind, row.source_id)
    if row.kind == "stage_promoted":
        from .stage_promotion import promoted_recipients
        return promoted_recipients(row.source_id)
    if row.kind == "judge_reminder":
        from .stage_judge_reminders import recipients as judge_recipients
        return judge_recipients(row)
    return reminder_recipients(row)


def reminder_revision(stage):
    """A moved deadline is a new reminder; an unrelated edit is not."""
    return int(stage.deadline.timestamp() // 60) if stage.deadline else 0


def reminder_recipients(row):
    """Members of active teams that may enter the stage and have not submitted it, before its deadline."""
    from apps.events.hackathons.team_models import HackathonTeam
    from apps.events.judging.options import option
    from .models_projects import HackathonSubmission
    from .models_stages import SubmissionStage
    from . import stage_runtime as runtime
    stage = SubmissionStage.objects.filter(pk=row.source_id, event_id=row.event_id).first()
    now = timezone.now()
    if (stage is None or reminder_revision(stage) != row.revision or not option(row.event, "stage_reminder_email")
            or not runtime.window_open(stage, row.event, None, now) or stage.deadline is None or now > stage.deadline):
        return ()
    stages = runtime.stages_for(row.event_id)
    members = set()
    for team in HackathonTeam.objects.filter(event_id=row.event_id).exclude(state="disbanded").order_by("pk"):
        project = HackathonSubmission.objects.filter(event_id=row.event_id, team=team).first()
        entry = runtime.entry(project, stage)
        if (entry and entry.current_snapshot_id) or runtime.gate(stage, stages, project) is not None:
            continue
        if project is not None and project.state not in ("draft", "submitted"):
            continue
        members.update(team.memberships.filter(state="active").values_list("member_id", flat=True))
    return tuple(sorted(members))


def render(envelope):
    from apps.integrations.notification_links import local_link
    link = local_link(envelope.makerspace, "member")
    if envelope.event == "stage_promoted":
        return {"subject": gettext("A place opened up: your team is through"),
                "text": gettext("A shortlisted team withdrew and your team takes its place. Open the event for the next stage."),
                "link": link}
    if envelope.event == "judge_reminder":
        return {"subject": gettext("Judging is waiting for you"),
                "text": gettext("You still have projects to review in an open judging round. Open the event to continue."),
                "link": link}
    if envelope.event == "stage_shortlisted":
        return {"subject": gettext("Your team made the shortlist"),
                "text": gettext("Your team was shortlisted. Open the event to see the next stage and its deadline."), "link": link}
    if envelope.event == "stage_not_shortlisted":
        return {"subject": gettext("Shortlist results are out"),
                "text": gettext("Your team was not shortlisted for the next stage this time. Your earlier submissions stay "
                        "as you submitted them. Thank you for taking part."), "link": link}
    return {"subject": gettext("A submission deadline is coming up"),
            "text": gettext("Your team has not submitted the current stage yet. Open the event to submit before the deadline."),
            "link": link}


def remind_due_stages(now=None, limit=100):
    """Queue one reminder per stage whose deadline falls within the next 24 hours (idempotent)."""
    from apps.events.judging.boundary import notice
    from apps.events.judging.options import options_for
    from .models_stages import SubmissionStage
    from apps.makerspaces.scheduled_scope import live_space_ids
    now = now or timezone.now()
    due = (SubmissionStage.objects.select_related("event__makerspace")
           .filter(deadline__gt=now, deadline__lte=now + REMINDER_WINDOW, event__status="published",
                   event__makerspace_id__in=live_space_ids("events"))
           .order_by("deadline", "pk")[:limit])
    queued = 0
    for stage in due:
        options = options_for(stage.event_id)
        if options is None or not options.stage_reminder_email:
            continue
        try:
            from .ports import boundary
            with boundary().locked(actor=None, event_id=stage.event_id, team_id=None, action="stage_reminder") as ctx:
                notice(ctx.event, "stage_deadline_reminder", stage.pk, reminder_revision(stage))
                queued += 1
        except Exception:
            logger.warning("event_stage_reminder_deferred", extra={"event_id": stage.event_id, "stage_id": stage.pk})
    from .stage_judge_reminders import remind_judges  # S15 rides the same sweep.
    return queued + remind_judges(now)
