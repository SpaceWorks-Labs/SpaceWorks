"""Signed Device Adapter API v1 routes, ``/api/v1/device/adapter/v1/...`` (decisions 310-312).

Authentication, replay protection, revocation and tenant gating are the existing signed device protocol; every
route is listed in ``route_registry_adapter`` (default-deny, ``devices.E001``). All of them answer 404 unless the
makerspace has the `machines.integrations` switch (and, per capability, its child switch). Bodies are validated
against the JSON Schemas published in ``docs/device-adapters/schemas``.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response

from apps.devices import services_adapter_access as access
from apps.devices import services_adapter_commands as commands
from apps.devices import services_adapter_hello as hello
from apps.devices import services_adapter_sessions as sessions
from apps.devices import services_adapter_status as status
from apps.devices.adapter_access import adapter_device
from apps.devices.errors import DeviceErrorSerializer
from apps.devices.openapi_adapter import REQUESTS, RESPONSES
from apps.devices.views_adapter_base import SignedAdapterView, SignedCredentialView

TAG = "Device adapter API"
ERRORS = {code: OpenApiResponse(DeviceErrorSerializer, description=text) for code, text in (
    (400, "invalid_payload (the body does not match the published JSON Schema) or a typed adapter code."),
    (401, "Authentication, signature, timestamp or replay refused."),
    (403, "Device revoked, key rotated, or tenant unavailable."),
    (404, "The `machines.integrations` switch (or the capability's child switch) is off, the device is not an "
          "adapter, or the target is not this adapter's own binding."),
    (409, "A typed conflict (lease_mismatch, unsupported_target, session_closed, job_not_acknowledged...); "
          "see docs/device-adapters/errors.md."),
    (410, "The lease expired (lease_expired) or the artifact is gone (artifact_expired)."),
    (413, "artifact_too_large, frame_too_large."), (423, "Tenant frozen for migration."),
    (429, "rate_limited (detections; slow down)."), (503, "storage_unavailable: object storage is down; retry."))}


def _doc(summary, request=None, response=None, code=200):
    """``request``/``response`` are keys of ``openapi_adapter``; ``request=None`` is a deliberately bodyless write
    (listed in ``openapi_contract.registry_bodyless``)."""
    return extend_schema(tags=[TAG], summary=summary, request=REQUESTS[request] if request else None,
                         responses={code: RESPONSES[response] if response else OpenApiTypes.OBJECT, **ERRORS})


class AdapterHelloView(SignedAdapterView):
    @_doc("Declare the adapter's kind and capabilities; returns its bindings (signed)", "hello", "hello")
    def post(self, request):
        return Response(hello.hello(request.user, request.data))


class AdapterBindingsView(SignedAdapterView):
    @_doc("List the targets this adapter serves, with their capabilities (signed)", response="bindings")
    def get(self, request):
        device = adapter_device(request.user)
        return Response({"bindings": hello.bindings_for(device)})


class AdapterStatusView(SignedAdapterView):
    @_doc("Report the normalised status of bound targets (signed, idempotent, throttled)", "status", "status")
    def post(self, request):
        return Response(status.store_status(request.user, request.data))


class AdapterEventsView(SignedAdapterView):
    @_doc("Append typed events, idempotent by operation_id (signed)", "events", "events")
    def post(self, request):
        return Response(status.ingest_events(request.user, request.data))


class AdapterCommandLeaseView(SignedAdapterView):
    @_doc("Lease the next queued command for this adapter (signed)", response="command_lease")
    def post(self, request):
        return Response(commands.lease(request.user))


class AdapterCommandAckView(SignedAdapterView):
    @_doc("Acknowledge a leased command with its outcome (signed)", "command_ack", "command_ack")
    def post(self, request, pk):
        return Response(commands.acknowledge(request.user, pk, request.data))


class AdapterAccessAuthorizeView(SignedCredentialView):
    @_doc("Decide whether a credential may use a machine or open a door (signed)", "access", "access")
    def post(self, request):
        return Response(access.authorize(request.user, request.data))


class AdapterSessionStartView(SignedCredentialView):
    @_doc("Start a metered machine session through the machine-session service (signed)", "session_start",
          "access")
    def post(self, request):
        return Response(sessions.start(request.user, request.data))


class AdapterSessionStopView(SignedAdapterView):
    @_doc("Stop a session this adapter started (signed)", "session_stop", "session_stop")
    def post(self, request, pk):
        return Response(sessions.stop(request.user, pk, request.data))


class AdapterUsageLogView(SignedAdapterView):
    @_doc("Record one immutable usage record, idempotent by operation_id (signed)", "usage", "usage")
    def post(self, request):
        return Response(sessions.log_usage(request.user, request.data))
