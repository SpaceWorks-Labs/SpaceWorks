"""Source-gate participation for the reimbursement, staged-form and core payout workers.

Each task only discovers candidate IDs outside a boundary; every per-subject write
re-enters the owning tenant's boundary before fences or domain locks, so one frozen
or refused tenant is skipped without blocking the rest of the page.
"""

TASK_INTERNAL_PARTICIPANTS = {
    "apps.event_reimbursements.tasks.sweep_deadlines_task": (
        "Excludes non-open source gates, then each sweep_one/defer step enters the event "
        "host's prepared boundary_tenant_write before fences and programme locks."
    ),
    "apps.events.staged_forms.tasks.reconcile_stage_forms_task": (
        "Each event reconciliation enters boundary_tenant_write for its host before key "
        "preparation, fences and stage locks."
    ),
    "apps.events.staged_forms.tasks.recover_stage_files_task": (
        "Each leased asset validation enters its host's boundary_tenant_write; scanner and "
        "storage I/O run outside row locks."
    ),
    "apps.events.staged_forms.tasks.sweep_stage_file_retention_task": (
        "Retention takes the retained shared_boundary per cleanup locator; permanent FK-free "
        "locators keep deleting bytes after MIGRATED_OUT or purge."
    ),
    "apps.payments.event_payouts.tasks.sweep_retention_task": (
        "Core finance retention: each asset/obligation enters worker_boundary.prepared_scope "
        "for its host; the deployment cursor is coordination only."
    ),
    "apps.payments.event_payouts.tasks.recover_finance_work_task": (
        "Upload validation and permanent locator cleanup enter the asset host's prepared "
        "scope; cleanup locators are FK-free deployment coordination."
    ),
    "apps.payments.event_payouts.tasks.run_due_retention_task": (
        "Targeted retention for one obligation or asset uses the same per-host prepared "
        "scope as the periodic sweep."
    ),
}


def gate_tasks(internal):
    duplicate = set(internal) & set(TASK_INTERNAL_PARTICIPANTS)
    if duplicate:
        raise RuntimeError(f"Duplicate reimbursement task gate declarations: {sorted(duplicate)}")
    internal.update(TASK_INTERNAL_PARTICIPANTS)
