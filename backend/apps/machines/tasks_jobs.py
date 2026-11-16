"""Machine job-flow sweep (lane L12): quotes, prepaid jobs and pickup reminders."""

from celery import shared_task


@shared_task(name="apps.machines.tasks_jobs.sweep_job_flow_task")
def sweep_job_flow_task():
    from apps.machines.job_sweeps import run_job_flow_sweep
    return run_job_flow_sweep()
