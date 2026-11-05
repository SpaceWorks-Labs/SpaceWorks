"""Idempotent event-clock deadline task; G registers worker and cloud schedules."""
from django.utils import timezone
from apps.audit.services import record
from .models_projects import HackathonSubmission
from .ports import boundary


def lock_event_submissions(*, event_id, now=None, limit=100):
    now = now or timezone.now()
    identities = tuple(HackathonSubmission.objects.filter(event_id=event_id, state="submitted")
                       .order_by("pk").values_list("pk", "team_id")[:min(max(limit, 1), 500)])
    count = 0
    for identity, team_id in identities:
        with boundary().locked(actor=None, event_id=event_id, team_id=team_id, action="deadline_lock") as context:
            from .stage_runtime import team_cutoff
            cutoff = team_cutoff(context)  # The last stage, or this team's later extension (#178, S2).
            if now <= cutoff:
                continue
            project = HackathonSubmission.objects.select_for_update().get(pk=identity, event_id=event_id)
            if project.state != "submitted" or not project.current_snapshot_id:
                continue
            project.state, project.locked_at = "locked", cutoff
            project.version += 1
            project.save(update_fields=["state", "locked_at", "version"])
            record(None, "event.submission_locked", makerspace=context.event.makerspace, target=project,
                   meta={"version": project.version, "snapshot_id": project.current_snapshot_id})
            from .notifications import enqueue_locked
            enqueue_locked(project=project, action="lock")
            count += 1
    return count
