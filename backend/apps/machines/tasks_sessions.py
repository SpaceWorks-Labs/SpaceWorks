"""Machine-session sweep (lane L23): auto-stop at max length, check-out and closing."""

from celery import shared_task


@shared_task(name="apps.machines.tasks_sessions.sweep_machine_sessions_task")
def sweep_machine_sessions_task():
    from apps.machines.sessions_sweep import run_session_sweep
    return run_session_sweep()
