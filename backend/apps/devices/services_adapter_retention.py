"""Adapter byte and telemetry retention, one tenant boundary per space (NCA audit 0.12.0).

The retention services (`services_adapter_history.sweep`, `services_adapter_artifacts.purge_expired`,
`services_adapter_media.purge_recordings`) delete tenant rows and objects. Run deployment-wide from Celery they
must not write into a space whose source gate is closed (tenant migration, pause), so each space is entered
through `fanout_tenant_write`, which also sets that space's RLS scope. A frozen space is skipped and counted, and
its rows wait for the next run. Retention deliberately ignores the adapters switch: bytes must still expire after
a space turns adapters off (`task_sources`: platform).
"""
from django.utils import timezone

OPERATION = "devices.adapter_retention"


def _spaces(*querysets):
    found = set()
    for queryset in querysets:
        found |= set(queryset.values_list("makerspace_id", flat=True).distinct().order_by())
    return sorted(found)


def sweep_media(now=None):
    """Telemetry downsampling/expiry and artifact retention, per space. Returns counters."""
    from apps.devices import services_adapter_artifacts as artifacts, services_adapter_history as history
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    now = now or timezone.now()
    counts = {"telemetry": 0, "artifacts": 0, "skipped": 0}
    for space_id in _spaces(history.due_points(now), artifacts.due_artifacts(now)):
        with fanout_tenant_write(space_id, operation=OPERATION, counts=counts) as should_process:
            if not should_process:
                continue
            counts["telemetry"] += history.sweep(now, space_id=space_id)
            counts["artifacts"] += artifacts.purge_expired(now, space_id=space_id)
    return counts


def sweep_recordings(now=None):
    """Camera recordings past retention, per space. Returns counters."""
    from apps.devices.services_adapter_media import due_recordings, purge_recordings
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    now = now or timezone.now()
    counts = {"purged": 0, "skipped": 0}
    for space_id in _spaces(due_recordings(now)):
        with fanout_tenant_write(space_id, operation=OPERATION, counts=counts) as should_process:
            if not should_process:
                continue
            counts["purged"] += purge_recordings(now, space_id=space_id)
    return counts
