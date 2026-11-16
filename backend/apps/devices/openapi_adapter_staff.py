"""OpenAPI bodies of the staff (``/api/v1/admin/``) and viewer (``/api/v1/member/``) adapter routes whose answers are
plain dicts built by a service rather than a serializer. Same approach as ``openapi_adapter``: open objects naming the
documented fields (the console ignores fields it does not know), and the viewer's signal body is the validator's own
``media.stream`` SIGNAL schema.
"""
from drf_spectacular.utils import inline_serializer
from rest_framework import serializers

from apps.devices.adapters.capability import TARGET_TYPES
from apps.devices.adapters.caps import media_stream
from apps.devices.adapters.schema import UUID
from apps.devices.openapi_adapter import answer, body

S, I, B, N, OBJ = {"type": "string"}, {"type": "integer"}, {"type": "boolean"}, {"type": "number"}, {"type": "object"}
DT = {"type": "string", "format": "date-time"}


def page(name, item_serializer):
    """The DRF page envelope (``count``/``next``/``previous``/``results``) around ``item_serializer``.

    These lists are paginated with ``PageNumberPagination`` inside an ``APIView``, which drf-spectacular cannot see,
    so a bare ``Serializer(many=True)`` would document a plain array while the server answers a page (NCA audit).
    """
    return inline_serializer(name=name, fields={
        "count": serializers.IntegerField(), "next": serializers.CharField(allow_null=True),
        "previous": serializers.CharField(allow_null=True), "results": item_serializer(many=True)})


def _array(items):
    return {"type": "array", "items": items}


def _nullable(schema):
    return {**schema, "nullable": True}


# The binding's own overrides, and every effective key with where it comes from (services_adapter_safety.config_view).
EFFECTIVE = {"type": "object", "additionalProperties": answer(
    {"value": {}, "source": {"type": "string", "enum": ["type", "binding"]}}, ["value", "source"])}
# The latest normalised status report: state and time plus the reported (capability-dependent) fields.
STATUS = _nullable(answer({"state": S, "observed_at": DT}, ["state", "observed_at"]))
CACHE = _nullable(answer({"version": I, "entry_count": I, "issued_at": DT, "expires_at": DT,
                          "reconciled_at": _nullable(DT)}))
BINDING = answer({
    "id": UUID, "target_type": {"type": "string", "enum": list(TARGET_TYPES)}, "machine_id": _nullable(I),
    "target_id": S, "external_ref": S, "capabilities": _array(S), "enabled": B, "status": STATUS, "config": OBJ,
    "effective_config": EFFECTIVE, "offline_cache": CACHE}, ["id", "target_type", "capabilities", "enabled"])
ADAPTER = answer({
    "id": UUID, "name": S, "status": S, "last_seen_at": _nullable(DT), "adapter_kind": _nullable(S), "vendor": S,
    "software_version": S, "capabilities": _array(answer({"name": S, "version": I}, ["name"])), "config_version": I,
    "hello_at": _nullable(DT), "firmware": S, "health": S, "health_at": _nullable(DT), "online": B,
    "offline_since": _nullable(DT), "telemetry_dropped_7d": I, "bindings": _array(BINDING)},
    ["id", "name", "status", "online", "bindings"])
SIGNAL = answer({"n": I, "from": S, "kind": S, "sdp": S, "candidate": S}, ["n", "kind"])
ICE = answer({"urls": _array(S), "username": S, "credential": S}, ["urls"])
ARTIFACT_URL = answer({"url": S, "content_type": S, "kind": S}, ["url", "content_type", "kind"])

REQUESTS = {"viewer_signal": body(media_stream.SIGNAL)}
RESPONSES = {
    "adapter_list": answer({"results": _array(ADAPTER)}, ["results"]),
    "adapter": ADAPTER,
    "binding_detail": answer({
        "id": UUID, "device": UUID, "target_type": S, "machine": _nullable(I), "target_id": S, "external_ref": S,
        "capabilities": _array(S), "enabled": B, "created_at": DT, "config": OBJ, "effective_config": EFFECTIVE,
        "status": STATUS}, ["id", "device", "target_type", "capabilities", "enabled", "status"]),
    "binding_config": answer({"id": UUID, "config": OBJ, "effective_config": EFFECTIVE},
                             ["id", "config", "effective_config"]),
    "position": answer({"pose": _nullable(OBJ)}, ["pose"]),
    "job_created": answer({"job_id": UUID, "state": S}, ["job_id", "state"]),
    "webhook": answer({
        "url": S, "enabled": B, "include_data": B, "secret_version": I, "consecutive_failures": I,
        "disabled_at": _nullable(DT), "disabled_reason": S, "last_success_at": _nullable(DT),
        "secret": {"type": "string", "description": "Present only in the answer that created or rotated it."}},
        ["url", "enabled", "include_data", "secret_version"]),
    "webhook_deliveries": answer({"results": _array(answer({
        "id": UUID, "type": S, "status": S, "attempts": I,
        "last_status_code": {**_nullable(I), "description": "Only on a delivered push; null for a failed attempt."},
        "last_error": {"type": "string", "description": "`delivery_failed` or `url_refused`; empty once delivered."},
        "created_at": DT, "delivered_at": _nullable(DT)}, ["id", "type", "status"]))}, ["results"]),
    "type_profile": answer({"machine_type_id": I, "config": OBJ, "updated_at": _nullable(DT)},
                           ["machine_type_id", "config"]),
    "artifact_url": ARTIFACT_URL,
    "telemetry": answer({"binding_id": UUID, "series": _array(S), "selected": S, "resolution": I,
                         "points": _array(answer({"ts": DT, "avg": N, "min": N, "max": N, "n": I}))},
                        ["binding_id", "series", "resolution", "points"]),
    "command_queued": answer({"command_id": UUID, "status": S}, ["command_id", "status"]),
    "talk": answer({"n": I, "active": B}, ["n", "active"]),
    "viewer_poll": answer({"signals": _array(SIGNAL), "ice_servers": _array(ICE)}, ["signals", "ice_servers"]),
    "viewer_signal": answer({"n": I}, ["n"]),
    "frame": answer({"content_type": _nullable(S), "data": _nullable(S)}, ["content_type", "data"]),
}
