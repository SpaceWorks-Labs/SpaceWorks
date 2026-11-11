"""Beat-less-safe membership renewal sweep (registered in `run_scheduled_tasks`)."""

from celery import shared_task


@shared_task(name="apps.makerspaces.tasks_membership.run_membership_renewals_task")
def run_membership_renewals_task():
    from apps.makerspaces.guest_pass_sweeps import run_guest_pass_sweeps
    from apps.makerspaces.membership_plan_services import run_membership_renewals

    counts = run_membership_renewals()
    # Decision 223: guest-pass expiry and notices ride this hourly sweep (no extra beat entry), after the
    # renewal pass, each space in its own skip-and-count tenant boundary. A failure here never hides renewals.
    try:
        run_guest_pass_sweeps()
    except Exception:  # pragma: no cover - the sweep logs per space; this guards the task itself
        import logging
        logging.getLogger(__name__).exception("guest_pass_sweeps_failed")
    try:
        from apps.events.join_followup import send_join_followups  # decision 223 (k): post-event join notice
        send_join_followups()
    except Exception:  # pragma: no cover - per-space boundary inside; this guards the task itself
        import logging
        logging.getLogger(__name__).exception("join_followup_sweep_failed")
    return counts
