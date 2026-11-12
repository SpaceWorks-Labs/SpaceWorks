"""The capability registry. Adding a capability = one module under ``caps/`` + one line here."""
from .caps import (access_authorize, access_cache, artifact_upload, checkout_kiosk, config_push, consumables, control,
                   detection_report, diagnostics, door_access, events, file_fetch, job_dispatch, label_print,
                   locate_calibrate, locate_indicate, maintenance_report, media_audio, media_snapshot, media_stream,
                   media_talk, safety, scan_report, sensor_report, session, status, telemetry, telemetry_history,
                   time_sync, usage_log)
from .schema import EPOCH, UUID, errors, obj

CAPABILITIES = {cap.name: cap for cap in (
    status.CAPABILITY, telemetry.CAPABILITY, events.CAPABILITY, job_dispatch.CAPABILITY, file_fetch.CAPABILITY,
    control.CAPABILITY, access_authorize.CAPABILITY, session.CAPABILITY, session.CAPABILITY_STOP,
    usage_log.CAPABILITY, consumables.CAPABILITY, safety.CAPABILITY, maintenance_report.CAPABILITY,
    locate_indicate.CAPABILITY, locate_calibrate.CAPABILITY, label_print.CAPABILITY, scan_report.CAPABILITY,
    sensor_report.CAPABILITY, door_access.CAPABILITY, media_snapshot.CAPABILITY, media_stream.CAPABILITY,
    checkout_kiosk.CAPABILITY, media_audio.CAPABILITY, media_talk.CAPABILITY, artifact_upload.CAPABILITY,
    detection_report.CAPABILITY, telemetry_history.CAPABILITY, diagnostics.CAPABILITY, access_cache.CAPABILITY,
    config_push.CAPABILITY, time_sync.CAPABILITY)}
KINDS = ("fdm_printer", "resin_printer", "laser", "cnc", "generic", "shelf_pointer", "label_printer", "scanner",
         "door", "sensor", "kiosk")
PROTOCOL_VERSION = 1


def known(name):
    return name in CAPABILITIES


def command_schema(capability, command):
    cap = CAPABILITIES.get(capability)
    return cap.commands.get(command) if cap else None


def event_schema(capability_names, event_type):
    for name in capability_names:
        cap = CAPABILITIES.get(name)
        if cap and event_type in cap.events:
            return name, cap.events[event_type]
    return None, None


def status_schema(capability_names):
    """Status item schema for a binding: the status props plus those of its other capabilities."""
    props = {"binding_id": UUID, "observed_at": EPOCH}
    for name in ("status", *capability_names):
        cap = CAPABILITIES.get(name)
        if cap:
            props.update(cap.status_props)
    return obj(props, ["binding_id", "observed_at", "state"])


def validate(schema, value):
    return errors(schema, value)
