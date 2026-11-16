"""Device Celery tasks. Every sweep fans out with one source-gate boundary per tenant (``fanout_tenant_write``);
the single push takes its tenant from the delivery row (``TASK_TENANT_RESOLVERS``)."""

from celery import shared_task

from apps.devices.services_offline import scan_offline_devices

# Decision 332(a): per-task time limits on the outbound adapter tasks (no global Celery default yet). One push is a
# single POST with a 5 s timeout; the sweep sends at most SWEEP_BATCH of them and the rest wait for the next minute.
# The hard limit stays below the delivery lease (services_adapter_webhook.LEASE_SECONDS) so a killed push is retried
# only after its lease has expired, never while it might still be in flight.
PUSH_SOFT_SECONDS, PUSH_HARD_SECONDS = 30, 45
PUSH_SWEEP_SOFT_SECONDS, PUSH_SWEEP_HARD_SECONDS = 240, 300


@shared_task
def scan_offline_devices_task():
    return scan_offline_devices()


@shared_task
def adapter_safety_sweep_task():
    """Idle auto-off and session-ending notices, from the binding safety config (server-side)."""
    from apps.devices.services_adapter_safety import sweep_safety
    return sweep_safety()


@shared_task
def purge_adapter_recordings_task():
    """Delete camera recordings past their retention window (one tenant boundary per space)."""
    from apps.devices.services_adapter_retention import sweep_recordings
    return sweep_recordings()


@shared_task
def adapter_media_sweep_task():
    """Telemetry downsampling and artifact retention (decision 321)."""
    from apps.devices.services_adapter_retention import sweep_media
    return sweep_media()


@shared_task(soft_time_limit=PUSH_SOFT_SECONDS, time_limit=PUSH_HARD_SECONDS)
def deliver_adapter_webhook_task(delivery_id):
    """One push attempt (retries are driven by the sweep with backoff)."""
    from apps.devices.services_adapter_webhook import deliver
    return deliver(delivery_id)


@shared_task(soft_time_limit=PUSH_SWEEP_SOFT_SECONDS, time_limit=PUSH_SWEEP_HARD_SECONDS)
def adapter_webhook_sweep_task():
    """Retry due pushes and prune the delivery log."""
    from apps.devices.services_adapter_webhook import sweep
    return sweep()
