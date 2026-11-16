"""Audit metadata ids written by the Device Adapter API (decision 312).

The Device and the machine session travel with the space, so their ids remap. Every adapter row (binding, command,
credential, usage record, watch) except the ShelfCheck is OMITTED from a dump (device-bound state), and a member id stays source
provenance like every other account id in audit metadata, so those ids are typed source-local snapshots.
"""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP
S = AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT

DEVICE_ACTIONS = ("hello", "bound", "unbound", "command_queued", "command_leased", "command_acked", "access_decided",
                  "session_stopped", "usage_logged", "pose_saved", "pose_cleared", "watch_started", "watch_ended",
                  "job_file_fetched", "kiosk_started", "kiosk_ended", "label_queued", "watch_recording_requested",
                  "watch_recording_stored", "watch_recording_purged", "watch_viewed", "config_set", "auto_apply_set",
                  "webhook_set", "webhook_rotated", "webhook_disabled", "profile_set", "indicated",
                  "audio_started", "talk_started", "talk_stopped", "artifact_requested", "artifact_stored",
                  "artifact_viewed", "artifact_purged", "access_cache_issued", "offline_decisions_reconciled",
                  "config_pushed", "config_acked", "shelf_shown", "shelf_cleared")
ROW_IDS = {
    "binding_id": "devices.AdapterBinding", "command_id": "devices.AdapterCommand",
    "usage_id": "devices.AdapterUsageLog", "watch_id": "devices.AdapterWatch",
    "artifact_id": "devices.AdapterArtifact",
}
SHELF_CHECK_ACTIONS = ("devices.shelf_check_saved",)

EDGES = {
    **{(f"devices.adapter_{action}", "device_id"): AuditReference(R, "devices.Device") for action in DEVICE_ACTIONS},
    ("devices.adapter_session_stopped", "session_id"): AuditReference(R, "machines.MachineSession"),
    **{(f"devices.adapter_{action}", key): AuditReference(S, label)
       for action in DEVICE_ACTIONS for key, label in ROW_IDS.items()},
    **{(f"devices.adapter_{action}", "member_id"): AuditReference(S, "accounts.User")
       for action in ("access_decided", "credential_set", "credential_removed")},
    **{(f"devices.adapter_{action}", "credential_id"): AuditReference(S, "devices.AdapterCredential")
       for action in ("credential_set", "credential_removed")},
    # Shelf checks (decision 331c): the ShelfCheck row travels in a dump (decision 337e), so its id remaps.
    **{(a, "shelf_check_id"): AuditReference(R, "devices.ShelfCheck") for a in SHELF_CHECK_ACTIONS},
    # Safety auto-off (decision 312): binding, queued command and device of the tripped adapter.
    ("devices.adapter_auto_off", "device_id"): AuditReference(R, "devices.Device"),
    ("devices.adapter_auto_off", "binding_id"): AuditReference(S, "devices.AdapterBinding"),
    ("devices.adapter_auto_off", "command_id"): AuditReference(S, "devices.AdapterCommand"),
    # Ids the adapter audit rows carry beyond the device (printer job, label command, profile machine type, watched request).
    ("devices.adapter_job_file_fetched", "job_id"): AuditReference(R, "devices.PrinterJob"),
    ("devices.adapter_label_queued", "label_command_id"): AuditReference(S, "devices.AdapterCommand"),
    ("devices.adapter_profile_set", "machine_type_id"): AuditReference(R, "machines.MachineType"),
    ("devices.adapter_watch_viewed", "service_request_id"): AuditReference(R, "machines.MachineServiceRequest"),
}
