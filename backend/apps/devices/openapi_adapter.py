"""OpenAPI bodies of the signed Device Adapter API, built from the SAME dicts the server validates with.

Request bodies are the validator's own schema dicts (the ones exported to ``docs/device-adapters/schemas``), so the
OpenAPI document, the published JSON Schemas and the runtime check cannot drift. ``openapi`` translates the few
draft 2020-12 spellings OpenAPI 3.0 does not accept: an empty ``required`` list is dropped and a ``type`` list such
as ``["boolean", "null"]`` becomes ``type`` plus ``nullable``. Responses are OPEN objects naming the documented
fields: adapters must ignore response fields they do not know (docs/device-adapters/versioning.md).
"""
from apps.devices.adapters import registry
from apps.devices.adapters.capability import TARGET_TYPES
from apps.devices.adapters.caps import (access_authorize, access_cache, artifact_upload, checkout_kiosk, config_push,
                                        job_dispatch, media_snapshot, media_stream, session, time_sync, usage_log)
from apps.devices.adapters.hello import CAPABILITY_DECLARATION, HELLO
from apps.devices.adapters.schema import EPOCH, UUID, obj
from apps.devices.services_adapter_commands import ACK as COMMAND_ACK
from apps.devices.services_adapter_core import MAX_ITEMS
from apps.devices.services_adapter_status import EVENT_ITEM


def openapi(schema):
    """A deep copy of ``schema`` that OpenAPI 3.0 accepts (the validator keeps using the original)."""
    out = {}
    for key, value in schema.items():
        if key == "required" and not value:
            continue
        if key == "type" and isinstance(value, list):
            kinds = [kind for kind in value if kind != "null"]
            if len(kinds) == 1:
                out["type"] = kinds[0]
            if "null" in value:
                out["nullable"] = True
        elif key == "properties":
            out[key] = {name: openapi(item) for name, item in value.items()}
        elif key in ("items", "additionalProperties") and isinstance(value, dict):
            out[key] = openapi(value)
        else:
            out[key] = value
    return out


def body(schema):
    """``extend_schema(request=...)`` value: a JSON body validated against ``schema``."""
    return {"application/json": openapi(schema)}


def answer(props, required=()):
    """An open response object (unknown fields may be added later; adapters ignore them)."""
    return openapi(obj(props, required, extra=True))


def _array(items, limit=None):
    return {"type": "array", "items": items, **({"maxItems": limit} if limit else {})}


def _nullable(schema):
    return {**schema, "nullable": True}


S, I, B, OBJ = {"type": "string"}, {"type": "integer"}, {"type": "boolean"}, {"type": "object"}
STATUS_ITEM = registry.status_schema(list(registry.CAPABILITIES))
RESULT = answer({"operation_id": UUID, "result": {"type": "string", "enum": ["stored", "duplicate"]}},
                ["operation_id", "result"])
OFFLINE_RESULT = answer({"operation_id": UUID, "result": {"type": "string", "enum": ["stored", "duplicate", "rejected"]},
                         "code": S}, ["operation_id", "result"])
BINDING = answer({"id": UUID, "target_type": {"type": "string", "enum": list(TARGET_TYPES)},
                  "machine_id": _nullable(I), "target_id": S, "external_ref": S, "capabilities": _array(S)},
                 ["id", "target_type", "capabilities"])
UPLOAD = answer({"url": S, "fields": OBJ, "method": S, "headers": OBJ}, ["url"])

REQUESTS = {
    "hello": body(HELLO),
    "status": body(obj({"items": _array(STATUS_ITEM, MAX_ITEMS)}, ["items"])),
    "events": body(obj({"events": _array(EVENT_ITEM, MAX_ITEMS)}, ["events"])),
    "command_ack": body(COMMAND_ACK),
    "access": body(access_authorize.REQUEST),
    "session_start": body(session.START),
    "session_stop": body(session.STOP),
    "usage": body(usage_log.LOG),
    "job_ack": body(job_dispatch.ACK),
    "job_progress": body(job_dispatch.PROGRESS),
    "job_report": body(job_dispatch.REPORT),
    "kiosk_start": body(checkout_kiosk.SESSION_START),
    "kiosk_scan": body(checkout_kiosk.SCAN),
    "kiosk_evidence": body(checkout_kiosk.EVIDENCE),
    "kiosk_issue": body(checkout_kiosk.ISSUE),
    "kiosk_return": body(checkout_kiosk.RETURN),
    "signal": body(media_stream.SIGNAL),
    "frame": body(media_snapshot.FRAME),
    "recording": body(media_stream.RECORDING),
    "artifact": body(artifact_upload.REQUEST),
    "offline": body(obj({"decisions": _array(access_cache.OFFLINE_DECISION, 100)}, ["decisions"])),
    "config_ack": body(config_push.ACK),
}

_ACCESS = openapi({**access_authorize.RESPONSE, "additionalProperties": True})
_SIGNAL = answer({"n": I, "from": S, "kind": S, "sdp": S, "candidate": S}, ["n", "kind"])
_ICE = answer({"urls": _array(S), "username": S, "credential": S}, ["urls"])
RESPONSES = {
    "hello": answer({
        "device_id": UUID, "protocol_version": I, "server_time": EPOCH, "config_version": I, "poll_seconds": I,
        "capabilities": _array(CAPABILITY_DECLARATION), "unknown_capabilities": _array(S), "bindings": _array(BINDING),
        "cache_keys": _array(answer({"kid": I, "public_key": S, "status": {"type": "string",
                                                                           "enum": ["current", "previous"]}}))},
        ["device_id", "protocol_version", "server_time", "config_version", "poll_seconds", "bindings"]),
    "bindings": answer({"bindings": _array(BINDING)}, ["bindings"]),
    "status": answer({"results": _array(answer({"binding_id": S, "result": {"type": "string", "enum": [
        "stored", "stale", "throttled", "unknown_binding"]}})), "config_version": I, "server_time": EPOCH},
        ["results", "config_version", "server_time"]),
    "events": answer({"results": _array(RESULT)}, ["results"]),
    "command_lease": answer({"command": _nullable(answer({
        "command_id": UUID, "binding_id": UUID, "capability": S, "command": S, "params": OBJ, "lease_token": S,
        "lease_expires_at": EPOCH}))}, ["command"]),
    "command_ack": answer({"command_id": UUID, "status": S}, ["command_id", "status"]),
    "access": _ACCESS,
    "session_stop": answer({"session_id": I, "stopped": B, "minutes": _nullable(I)}, ["session_id", "stopped"]),
    "usage": RESULT,
    "job_lease": answer({"job": _nullable(answer({
        "job_id": UUID, "lease_token": S, "lease_expires_at": EPOCH, "binding_id": S, "machine_id": I,
        "service_request_id": _nullable(I), "has_files": B}))}, ["job"]),
    "job_ack": answer({"job_id": UUID, "status": S}, ["job_id", "status"]),
    "job_progress": answer({"job_id": UUID, "result": S}, ["job_id", "result"]),
    "job_report": answer({"job_id": UUID, "state": S, "operation_id": UUID}, ["job_id", "state", "operation_id"]),
    "job_files": answer({"files": _array(answer({"file_id": I, "name": S, "content_type": S,
                                                 "size_bytes": _nullable(I), "kind": S, "url": S}))}, ["files"]),
    "kiosk_start": answer({"allowed": B, "decision": S, "reason": S, "session_id": S, "expires_in": I,
                           "member": answer({"display_name": S})}, ["allowed", "decision"]),
    "kiosk_end": answer({"ended": B}, ["ended"]),
    "kiosk_scan": answer({"action": {"type": "string", "enum": [
        "unknown", "checkout", "return", "checked_out_by_other", "ineligible"]}, "indicated": B}, ["action"]),
    "kiosk_evidence": answer({"evidence_id": I, "upload_url": S, "fields": OBJ, "object_key": S, "method": S,
                              "headers": OBJ}, ["evidence_id", "upload_url"]),
    "kiosk_loan": answer({"status": S, "public_token": S}, ["status"]),
    "signal_poll": answer({"signals": _array(_SIGNAL), "ice_servers": _array(_ICE), "record": B, "audio": B,
                           "talk": B, "announce_audio": B, "expires_at": EPOCH}, ["signals", "expires_at"]),
    "signal_sent": answer({"n": I}, ["n"]),
    "frame": answer({"stored": B}, ["stored"]),
    "recording": answer({"upload_url": S, "fields": OBJ, "object_key": S, "expires_at": EPOCH},
                        ["upload_url", "object_key", "expires_at"]),
    "artifact": answer({"artifact_id": UUID, "object_key": S, "upload": UPLOAD, "expires_at": EPOCH, "status": S,
                        "duplicate": B}, ["artifact_id"]),
    "artifact_done": answer({"artifact_id": UUID, "status": S}, ["artifact_id", "status"]),
    "access_cache": openapi(access_cache.CACHE_DOC),
    "offline": answer({"results": _array(OFFLINE_RESULT)}, ["results"]),
    "config": answer({"version": I, "config": OBJ}, ["version", "config"]),
    "config_ack": answer({"version": I, "outcome": _nullable(S)}, ["version"]),
    "time": openapi(time_sync.RESPONSE),
}
