"""Release 2 L12: source-gate declarations for the loan pickup and machine job sweeps."""

# The callables that open a per-tenant `fanout_tenant_write` skip-and-count boundary.
FANOUT = {
    "apps.hardware_requests.request_lifecycle.expire_due_requests": "Loan pickup expiry, one tenant at a time.",
    "apps.hardware_requests.pickup_reminders.remind_expiring_pickups": "Loan pickup-expiring reminders, one tenant at a time.",
    "apps.hardware_requests.waitlist.lapse_due_offers": "Loan waitlist offer lapses, one tenant at a time.",
    "apps.makerspaces.guest_pass_sweeps.run_guest_pass_sweeps": (
        "Guest-pass expiry, expiring notices and outstanding-item notices, one tenant at a time "
        "(rides the hourly membership sweep)."
    ),
    "apps.events.join_followup.send_join_followups": (
        "Post-event join notices to non-member attendees, one tenant at a time (rides the hourly membership sweep)."
    ),
    "apps.makerspaces.notifications_profile_open.send_open_notices": (
        "One-time open-profile notices, one tenant at a time (rides the hourly membership sweep)."
    ),
    "apps.events.venue_fee_retry.retry_unraised_venue_fees": ("Venue-fee retries for published events, one tenant at a time (batch 5, A12)."),
    "apps.machines.job_sweeps._each": "Machine job quote, pickup and prepay steps, one tenant at a time.",
}


def gate_tasks(internal, fanout):
    internal.update({
        "apps.hardware_requests.tasks_loans.sweep_loan_pickups_task": (
            "Each pickup expiry and waitlist lapse runs inside its own skip-and-count tenant boundary."
        ),
        "apps.machines.tasks_jobs.sweep_job_flow_task": (
            "Each job quote, pickup and prepay step runs inside its own skip-and-count tenant boundary."
        ),
    })
    fanout.update(FANOUT)
