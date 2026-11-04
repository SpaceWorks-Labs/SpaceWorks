"""Release 2 L12: source-gate declarations for the loan pickup and machine job sweeps."""

# The callables that open a per-tenant `fanout_tenant_write` skip-and-count boundary.
FANOUT = {
    "apps.hardware_requests.request_lifecycle.expire_due_requests": "Loan pickup expiry, one tenant at a time.",
    "apps.hardware_requests.waitlist.lapse_due_offers": "Loan waitlist offer lapses, one tenant at a time.",
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
