"""Fan-out (per-tenant sweep) participants of the source gate, split out of `gate_policy_tasks.py` at the 300-line
ceiling. `gate_policy_tasks` re-exports `FANOUT_GATE_PARTICIPANTS` (same object), so the barrel keeps resolving."""

from .gate_policy_replay import REPLAY_FANOUT_PARTICIPANTS


FANOUT_GATE_PARTICIPANTS = {
    "apps.events.judging.lifecycle.sweep_notices": "Each persisted result notice re-enters skip-and-count source boundary before delivery.",
    "apps.events.tasks_contributions.sweep_contributor_maintenance_task": "Contributor lease expiry, escalation and committed-notice recovery.",
    "apps.integrations.notification_media.cleanup_grants": (
        "Expired and consumed disclosure grants are deleted and audited inside each tenant gate."
    ),
    "apps.payments.bill_sweeper.issue_missing_bills": "Core bill recovery uses per-tenant skip-and-count source gates.",
    "apps.payments.refund_case_sweeper.rebuild_missed_refund_cases": "Refund-case rebuild uses per-tenant skip-and-count source gates.",
    "apps.payments.gateway_poll.run_gateway_poll": "Gateway poll uses per-tenant skip-and-count source gates.",
    "apps.makerspaces.profile_github_tasks.refresh_public_calendars": (
        "Public calendars refresh under the existing per-tenant GitHub source boundary; cache only."
    ),
    "apps.integrations.messaging.stops.append_stop_consents": "Optional consent annotations skip frozen tenants after committing sender-level STOP protection.",
    "apps.integrations.notification_legacy_ingress.inbound": "Per-tenant endpoint effects of a signed inbound skip frozen tenants; sender-level STOP already committed and the receipt stays held for recovery.",
    "apps.inventory.stock_snapshots.snapshot_inventory_stock": "Daily stock observations gate each tenant separately.",
    "apps.notifications.tasks.sweep_member_push": "Member push recovery gates each tenant separately.",
    "apps.accounts.account_purge.purge_account": "Account erasure and durable object cleanup gate each tenant separately.",
    "apps.integrations.broadcasts_worker.recover_for_tenants": "Recover durable campaigns and outboxes only inside each tenant's source gate.",
    "apps.data_export.subject_tasks.sweep_subject_exports_task": "Personal export recovery gates each tenant.",
    "apps.makerspaces.membership_admission_payments.sweep_admissions": (
        "Admission expiry and settlement retries use separate skip-and-count tenant boundaries."
    ),
    "apps.integrations.notification_retention.run_canonical_retention": (
        "Terminal addressed-leg cleanup gates each tenant separately."
    ),
    "apps.notifications.retention.run_notification_retention": (
        "Bounded inbox and terminal delivery cleanup gates each tenant separately."
    ),
    "apps.operations.reminder_sweeper.run_reminder_sweep": (
        "Shared source-local reminders; each tenant is gated before discovery or dispatch."
    ),
    **REPLAY_FANOUT_PARTICIPANTS,
    "apps.devices.services_offline.scan_offline_devices": "Device offline edges and auth-artifact retention.",
    "apps.data_export.tasks.purge_expired_exports_task": "Expired export cleanup.",
    "apps.evidence.abandoned_upload_cleanup.sweep_abandoned_evidence_uploads": (
        "Abandoned evidence-upload cleanup."
    ),
    "apps.evidence.services_retention.sweep_evidence_retention": (
        "Evidence object expiry."
    ),
    "apps.hardware_requests.services_return_reminders._run_legacy_return_reminders": (
        "Overdue loan reminders."
    ),
    "apps.makerspaces.tasks.refresh_github_contributions_task": "GitHub profile refresh.",
    "apps.makerspaces.membership_renewals.run_membership_renewals": (
        "Membership term expiry and renewal charges."
    ),
    "apps.operations.report_schedule_services.run_report_schedules": "Due scheduled report deliveries.",
    "apps.makerspaces.station_lease_cleanup.purge_expired_operator_leases": (
        "Expired kiosk operator lease cleanup."
    ),
    "apps.events.tasks_cloud.process_asset_work_task": "Bounded submission asset work.",
    "apps.events.tasks_cloud.resume_certificates_task": "Bounded certificate batch and render recovery.",
    "apps.admin_api.cloud_work.chunk": "Free-profile bulk-import page (one job per chunk).",
    "apps.integrations.mail_providers.channel_chunks.drain_channels": (
        "Free-profile legacy channel delivery (one row per chunk)."
    ),
    "apps.integrations.mail_providers.chunks._phase": "Free-profile contract envelope delivery (one per chunk).",
    "apps.integrations.mail_providers.outbox.drain": (
        "Free-profile mail drain; platform mail stays ungated."
    ),
    "apps.operations.cloud_jobs.rollups.chunk": "Free-profile report rollup finalisation.",
}
