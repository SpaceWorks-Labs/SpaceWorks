"""Public stage deadlines for the event page and the calendar feeds (#178, S13).

Only an enabled hackathon programme shows its stages, and only names and dates: rules, shortlists
and who submitted never leave the staff and team views.
"""
from .models_stages import SubmissionStage


def public_stages(event):
    from apps.events.hackathons.admission_models import HackathonConfig
    if not HackathonConfig.objects.filter(event=event, enabled=True).exists():
        return []
    from .stage_gallery import public_filters
    return [{"position": stage.position, "name": stage.name, "opens_at": stage.opens_at,
             "deadline": stage.deadline or event.ends_at, "filters": public_filters(stage)}
            for stage in SubmissionStage.objects.filter(event=event).order_by("position")]


def add_stage_deadlines(calendar, event, *, component_class, add_common, utc):
    """One short calendar entry per stage deadline, next to the event's own (#178)."""
    from datetime import timedelta
    from apps.events.hackathons.admission_models import HackathonConfig
    if not HackathonConfig.objects.filter(event=event, enabled=True).exists():
        return
    for row in SubmissionStage.objects.filter(event=event).order_by("position"):
        deadline = utc(row.deadline or event.ends_at)
        component = component_class()
        add_common(component, uid=f"event-{event.calendar_uid}-stage-{row.pk}@spaceworks",
                   title=f"{event.title}: {row.name} deadline", description=f"Submission deadline for {row.name}.",
                   location="", starts_at=deadline - timedelta(minutes=15), ends_at=deadline,
                   status="CANCELLED" if event.status == "cancelled" else "CONFIRMED",
                   sequence=event.calendar_sequence + row.version, updated_at=row.updated_at)
        calendar.add_component(component)
