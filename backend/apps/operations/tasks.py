from apps.operations.cloud_jobs import bounded
from celery import shared_task

from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import servable_queryset
from apps.operations.report_rollups import finalize_evidence_rollups
from apps.operations.tasks_reminders import run_reminder_sweep_task  # noqa: F401
from apps.operations.tasks_platform import run_platform_problem_checks_task
from apps.operations.tasks_admissions import sweep_membership_admissions_task  # noqa: F401
from apps.operations.tasks_platform_overview import compute_platform_overview_task  # noqa: F401


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def finalize_report_rollups_task(self):
    from apps.makerspaces.scheduled_scope import live_space_ids
    # Rollups feed reports: a space with reports off is skipped, and the cursor catches up
    # the missed days on the first run after reports come back on.
    spaces = servable_queryset(Makerspace.objects.filter(pk__in=live_space_ids("reports")))
    for makerspace in bounded.page(spaces, "rollup-spaces"):
        finalize_evidence_rollups(makerspace)
