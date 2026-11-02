"""Release 2 L12: source-gate declarations for the loan pickup and machine job sweeps."""


def gate_tasks(internal):
    internal.update({
        "apps.hardware_requests.tasks_loans.sweep_loan_pickups_task": (
            "Each pickup expiry and waitlist lapse runs inside its own skip-and-count tenant boundary."
        ),
        "apps.machines.tasks_jobs.sweep_job_flow_task": (
            "Each job quote, pickup and prepay step runs inside its own skip-and-count tenant boundary."
        ),
    })
