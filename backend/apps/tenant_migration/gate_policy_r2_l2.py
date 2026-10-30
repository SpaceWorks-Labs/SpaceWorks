"""Release-2 lane L2 source-gate declarations: every new task holds a per-tenant
skip-and-count (or event write / retention) boundary before it writes."""

PARTICIPANTS = {
    "apps.events.approval_digest.send_approval_digests_task": (
        "Each space's digest envelopes are emitted inside its own skip-and-count source boundary."
    ),
    "apps.events.submissions.integrity_jobs.sweep_integrity_checks_task": (
        "GitHub I/O runs outside locks; each check result is written under the event write boundary "
        "inside the space's skip-and-count source boundary."
    ),
    "apps.events.submissions.storage_reconcile.reconcile_event_storage_task": (
        "Each event is reconciled under the retention boundary (shared source boundary, fences, event lock)."
    ),
    "apps.notifications.escalation.escalate_unseen_task": (
        "Each space's escalation rows are written inside its own skip-and-count source boundary."
    ),
    "apps.integrations.destination_health.disable_dead_destinations_task": (
        "A dead room is switched off under tenant_write for its own makerspace."
    ),
    "apps.notifications.browser_alerts.deliver_browser_alert": (
        "Subscription bookkeeping is written inside the row's tenant skip-and-count source boundary."
    ),
}


def gate_tasks(participants):
    participants.update(PARTICIPANTS)
