"""NCA audit 0.12.0: source-gate declarations for the 0.12.0 device-adapter and transient-delivery tasks.

These seven tasks shipped without a declaration, so `validate_task_coverage` (and the safety sweep's
`fanout_tenant_write` call, `validate_fanout_gate_coverage`) failed, and at runtime every one of them ran under the
deployment-wide unscoped writer lock instead of its own tenant boundary.

* One push / one transient email: the tenant comes from the row the task is given (a platform email has no space
  and runs unbounded, exactly like `deliver_email_task`).
* The sign-in SMS: platform-global, sealed payload, no tenant row.
* The four adapter sweeps, and closing card photo batches stalled past expiry (`purge_expired_card_job_results`):
  one `fanout_tenant_write` per space; a frozen, paused or migrating space is skipped and counted, and its rows
  wait for the next run.
"""

TASKS = "apps.devices.tasks."


def gate_tasks(exemptions, internal, fanout, resolvers):
    resolvers[TASKS + "deliver_adapter_webhook_task"] = ("devices.AdapterWebhookDelivery", 0, "makerspace_id")
    resolvers["apps.integrations.tasks_transient.deliver_transient_email_task"] = (
        "integrations.EmailLog", 0, "makerspace_id"
    )
    exemptions["apps.integrations.tasks_transient.deliver_transient_sms_task"] = (
        "Platform-global sign-in/verification SMS from a sealed payload: reads no tenant row and writes only "
        "the platform SmsSendLog counter row (no makerspace)."
    )
    internal[TASKS + "adapter_safety_sweep_task"] = "Idle auto-off and session caps gate each tenant separately."
    internal[TASKS + "adapter_webhook_sweep_task"] = (
        "Push retries and delivery-log pruning gate each tenant separately; the POST runs outside any transaction."
    )
    internal[TASKS + "adapter_media_sweep_task"] = "Telemetry and artifact retention gate each tenant separately."
    internal[TASKS + "purge_adapter_recordings_task"] = "Recording retention gates each tenant separately."
    fanout["apps.devices.services_adapter_safety.sweep_safety"] = "Adapter idle auto-off and session caps."
    fanout["apps.devices.services_adapter_webhook.sweep"] = "Adapter push retries and delivery-log pruning."
    fanout["apps.devices.services_adapter_retention.sweep_media"] = "Adapter telemetry and artifact retention."
    fanout["apps.devices.services_adapter_retention.sweep_recordings"] = "Adapter camera recording retention."
    fanout["apps.card_designs.photo_batch_apply.expire_stalled"] = "Card photo batches stalled past their expiry."
    fanout["apps.machines.notifications_machine_access.notify_expiring"] = "Machine-access expiry reminders."
