"""Devices-module purge: authentication rows first, then identity and its history.

Runs inside the authorized purge context, so the DeviceEvent append-only trigger admits
the DELETE. Enrollments and replay nonces go before the Device rows they authenticate,
so no instant exists where a device survives without its revocation path. Printer failure
notes are scoped PII without a blind index.

Object storage: adapter artifacts and camera-watch recordings are private objects. Their
keys are collected under the purge lock by ``devices_private_keys`` (BOTH the final and
the staging key, since every presign lands on staging and a recording is never promoted)
and deleted after commit by the shared purge storage step, like every other module's
private keys. They used to be left behind: recordings of people survived the purge (M3).
"""
from apps.makerspaces.module_purge_collectors_single_model import _counts, _delete


def delete_adapter_rows(makerspace):
    """Device Adapter API rows, children before parents (credentials hold digests; poses hold calibration)."""
    from apps.devices import models as m

    counts, labels = {}, set()  # object bytes: devices_private_keys, deleted post-commit
    for key, model in (
        ("adapter_artifacts", m.AdapterArtifact), ("adapter_telemetry", m.AdapterTelemetryPoint), ("adapter_telemetry_drops", m.AdapterTelemetryDrop),
        ("adapter_config_versions", m.AdapterConfigVersion), ("adapter_access_caches", m.AdapterAccessCache),
        ("adapter_webhook_deliveries", m.AdapterWebhookDelivery), ("adapter_webhooks", m.AdapterWebhook),
        ("adapter_type_profiles", m.AdapterTypeProfile), ("adapter_watches", m.AdapterWatch), ("adapter_poses", m.AdapterPose), ("shelf_checks", m.ShelfCheck), ("adapter_commands", m.AdapterCommand),
        ("adapter_events", m.AdapterEvent), ("adapter_access_logs", m.AdapterAccessLog),
        ("adapter_usage_logs", m.AdapterUsageLog), ("adapter_statuses", m.AdapterStatus),
        ("adapter_credentials", m.AdapterCredential), ("adapter_bindings", m.AdapterBinding),
        ("adapter_profiles", m.AdapterProfile),
    ):
        counts[key], found = _delete(model.objects.filter(makerspace=makerspace))
        labels |= found
    return counts, labels


def devices_private_keys(makerspace, add):
    """Every adapter artifact and recording object of the space, final AND staging key (purged rows included)."""
    from apps.devices.models import AdapterArtifact, AdapterWatch
    from apps.machines.storage import staging_key

    artifacts = AdapterArtifact.objects.filter(makerspace=makerspace).values_list("object_key", flat=True)
    recordings = AdapterWatch.objects.filter(makerspace=makerspace).exclude(recording_key="").values_list(
        "recording_key", flat=True)
    for key in (*artifacts, *recordings):
        add(key)
        add(staging_key(key))


def devices_delete(makerspace, cursor):
    from apps.devices.models import Device, DeviceEnrollment, DeviceEvent, DeviceRequestNonce
    from apps.devices.models_integrations import MachineTypeIntegration

    from .module_purge_collectors_7b import delete_printer_rows

    from .module_purge_collectors_7c import delete_label_commands

    label_counts = delete_label_commands(makerspace)
    label_models = label_counts.model_labels
    printer_counts, printer_labels = delete_printer_rows(makerspace)
    adapter_counts, adapter_labels = delete_adapter_rows(makerspace)
    nonces, nonce_labels = _delete(DeviceRequestNonce.objects.filter(device__makerspace=makerspace))
    enrollments, enrollment_labels = _delete(DeviceEnrollment.objects.filter(makerspace=makerspace))
    events, event_labels = _delete(DeviceEvent.objects.filter(makerspace=makerspace))
    devices, device_labels = _delete(Device.objects.filter(makerspace=makerspace))
    # Module audit 0.12.0: the per-type integration bindings are devices-module configuration; a purge
    # that left them would bring them back half-configured on reinstall.
    integrations, integration_labels = _delete(MachineTypeIntegration.objects.filter(makerspace=makerspace))
    return _counts(
        model_labels=label_models | printer_labels | adapter_labels | nonce_labels | enrollment_labels | event_labels | device_labels
        | integration_labels,
        **printer_counts,
        **adapter_counts,
        **label_counts,
        device_nonces=nonces,
        device_enrollments=enrollments,
        device_events=events,
        devices=devices,
        machine_type_integrations=integrations,
    )
