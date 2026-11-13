"""Device Adapter API (decision 312): audit action labels.

`devices.` is a wrapper-site namespace, so the dynamic policy denies metadata at read time; these entries carry
labels only and the raw audit row keeps its typed ids for auditors.
"""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("devices.adapter_hello", gettext_noop("Device adapter declared its capabilities")),
    P("devices.adapter_bound", gettext_noop("Device adapter bound to a target")),
    P("devices.adapter_unbound", gettext_noop("Device adapter unbound from a target")),
    P("devices.adapter_command_queued", gettext_noop("Command sent to a device adapter")),
    P("devices.adapter_command_leased", gettext_noop("Command delivered to a device adapter")),
    P("devices.adapter_command_acked", gettext_noop("Device adapter acknowledged a command")),
    P("devices.adapter_command_ack_refused", gettext_noop("Late device adapter acknowledgement refused")),
    P("devices.adapter_access_decided", gettext_noop("Device adapter access decision")),
    P("devices.adapter_session_stopped", gettext_noop("Machine session stopped by a device adapter")),
    P("devices.adapter_usage_logged", gettext_noop("Device adapter usage record")),
    P("devices.adapter_pose_saved", gettext_noop("Shelf-pointer pose saved")),
    P("devices.adapter_pose_cleared", gettext_noop("Shelf-pointer pose cleared")),
    P("devices.adapter_credential_set", gettext_noop("Adapter NFC or PIN credential set")),
    P("devices.adapter_credential_removed", gettext_noop("Adapter NFC or PIN credential disabled")),
    P("devices.adapter_watch_started", gettext_noop("Camera watch opened")),
    P("devices.adapter_watch_ended", gettext_noop("Camera watch ended")),
    P("devices.adapter_job_file_fetched", gettext_noop("Device adapter fetched a job file")),
    P("devices.adapter_auto_off", gettext_noop("Idle machine powered off by the safety sweep")),
    P("devices.adapter_kiosk_started", gettext_noop("Kiosk checkout session started")),
    P("devices.adapter_kiosk_ended", gettext_noop("Kiosk checkout session ended")),
    P("devices.adapter_label_queued", gettext_noop("Label print sent to a device adapter")),
    P("devices.adapter_watch_recording_requested", gettext_noop("Camera watch recording requested")),
    P("devices.adapter_watch_recording_stored", gettext_noop("Camera watch recording stored")),
    P("devices.adapter_watch_recording_purged", gettext_noop("Camera watch recording deleted after retention")),
    P("devices.adapter_auto_apply_set", gettext_noop("Adapter job auto-apply changed")),
    P("devices.adapter_profile_set", gettext_noop("Adapter safety profile of a machine type changed")),
    P("devices.adapter_webhook_set", gettext_noop("Adapter push endpoint set")),
    P("devices.adapter_webhook_rotated", gettext_noop("Adapter push secret rotated")),
    P("devices.adapter_webhook_disabled", gettext_noop("Adapter push endpoint disabled")),
    P("devices.adapter_shelf_shown", gettext_noop("Shelf pointer shown on a location")),
    P("devices.adapter_shelf_cleared", gettext_noop("Shelf pointer cleared")),
    P("devices.shelf_check_saved", gettext_noop("Shelf check saved")),
    P("devices.adapter_indicated", gettext_noop("Shelf lit for a kiosk scan")),
    P("devices.adapter_config_set", gettext_noop("Adapter safety settings changed")),
    P("devices.adapter_watch_viewed", gettext_noop("Camera watch joined by the job owner")),
    P("devices.adapter_audio_started", gettext_noop("Audio opened on a camera watch")),
    P("devices.adapter_talk_started", gettext_noop("Push-to-talk pressed on a device")),
    P("devices.adapter_talk_stopped", gettext_noop("Push-to-talk released on a device")),
    P("devices.adapter_artifact_requested", gettext_noop("Device adapter started an artifact upload")),
    P("devices.adapter_artifact_stored", gettext_noop("Device adapter artifact stored")),
    P("devices.adapter_artifact_viewed", gettext_noop("Private adapter artifact opened by staff")),
    P("devices.adapter_artifact_purged", gettext_noop("Adapter artifact deleted after retention")),
    P("devices.adapter_access_cache_issued", gettext_noop("Offline access cache issued to a device adapter")),
    P("devices.adapter_offline_decisions_reconciled", gettext_noop("Offline access decisions reported by a device adapter")),
    P("devices.adapter_config_pushed", gettext_noop("Config pushed to a device adapter")),
    P("devices.adapter_config_acked", gettext_noop("Device adapter acknowledged a config version")),
)
