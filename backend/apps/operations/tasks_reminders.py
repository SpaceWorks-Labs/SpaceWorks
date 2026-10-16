from celery import shared_task

from apps.operations.reminder_sweeper import run_reminder_sweep


@shared_task(name="apps.operations.tasks_reminders.run_reminder_sweep_task")
def run_reminder_sweep_task():
    from apps.integrations.broadcasts_worker import resume_broadcasts
    resume_broadcasts()
    return run_reminder_sweep()
