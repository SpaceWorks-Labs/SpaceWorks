"""Device Adapter API v1: tenant-dump field snapshot of the adapter models.

All of them are OMITTED from exports (data_export `classification_adapter` gives each reason), so none travels in a
tenant dump: a moved adapter re-enrolls and is re-bound on its target, poses are re-calibrated and credentials are
re-registered. The one exception is ``devices.ShelfCheck`` (decision 337e): a shelf walk is the space's own
operational record, so it is projected (rows kept as written, foreign keys remapped like any other).
"""
PROJECTED_LABELS = frozenset({"devices.ShelfCheck"})


FIELD_NAMES = {
    "devices.AdapterProfile": frozenset(
        "device makerspace protocol_version adapter_kind vendor software_version capabilities config_version "
        "hello_at firmware health health_at".split()),
    "devices.AdapterBinding": frozenset(
        "id makerspace device target_type machine target_id external_ref capabilities config enabled created_by "
        "created_at".split()),
    "devices.AdapterStatus": frozenset("binding makerspace state payload observed_at received_at".split()),
    "devices.AdapterCommand": frozenset(
        "id makerspace device binding device_key_version capability command params status attempts "
        "lease_token_digest lease_expires_at expires_at result_code completed_at created_by created_at".split()),
    "devices.AdapterEvent": frozenset(
        "id makerspace device binding operation_id event_type capability data observed_at received_at".split()),
    "devices.AdapterCredential": frozenset(
        "id makerspace user kind digest label failed_attempts locked_until last_used_at disabled_at created_by "
        "created_at".split()),
    "devices.ShelfCheck": frozenset(
        "id makerspace checked_by scope_label entries ok_count attention_count created_at".split()),
    "devices.AdapterPose": frozenset(
        "id makerspace binding target_type target_id pose note saved_by updated_at".split()),
    "devices.AdapterAccessLog": frozenset(
        "id makerspace device binding member credential_type allowed reason session_id_snapshot offline operation_id created_at".split()),
    "devices.AdapterUsageLog": frozenset(
        "id makerspace device binding operation_id session_id_snapshot started_at ended_at active_minutes "
        "idle_minutes outcome error_code consumptions created_at".split()),
    "devices.AdapterArtifact": frozenset(
        "id makerspace binding operation_id kind content_type size_bytes object_key status service_request_id "
        "session_id command_id captured_at created_at completed_at expires_at purged_at".split()),
    "devices.AdapterTelemetryPoint": frozenset("id makerspace binding series resolution ts avg min max n".split()),
    "devices.AdapterTelemetryDrop": frozenset("id makerspace day count".split()),
    "devices.AdapterConfigVersion": frozenset(
        "id makerspace device version config created_by created_at ack_outcome ack_detail acked_at".split()),
    "devices.AdapterAccessCache": frozenset(
        "binding makerspace version entry_count issued_at expires_at reconciled_at offline_decisions".split()),
    "devices.AdapterWebhook": frozenset(
        "device makerspace url enabled secret_version include_data consecutive_failures disabled_at disabled_reason "
        "last_success_at created_by created_at".split()),
    "devices.AdapterWebhookDelivery": frozenset(
        "id makerspace device event_type envelope status attempts next_attempt_at last_status_code last_error "
        "created_at delivered_at".split()),
    "devices.AdapterTypeProfile": frozenset("id makerspace machine_type config updated_by updated_at".split()),
    "devices.AdapterWatch": frozenset(
        "id makerspace binding viewer status signals record recording_key recording_expires_at "
        "recording_purged_at expires_at created_at ended_at audio talk audio_notice_ack talk_presses".split()),
}
