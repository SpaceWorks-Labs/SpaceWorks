"""Signed Device Adapter API v1 routes for the media and data capabilities (decision 321): artifact upload, offline
access cache and its reconciliation, remote config and signed time. Same authentication, tenant gating and
404-when-off behaviour as ``views_adapter``; each is listed in ``route_registry_adapter`` and delegates to a service."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response

from apps.devices import services_adapter_artifacts as artifacts
from apps.devices import services_adapter_config as config
from apps.devices import services_adapter_offline as offline
from apps.devices.openapi_adapter import RESPONSES
from apps.devices.services_adapter_core import AdapterError
from apps.devices.views_adapter import ERRORS, TAG, _doc
from apps.devices.views_adapter_base import SignedAdapterView

_BINDING = OpenApiParameter("binding_id", OpenApiTypes.UUID, required=True)
_NONCE = OpenApiParameter("nonce", OpenApiTypes.STR, required=True,
                         description="Required fresh adapter-chosen nonce (16-64 of A-Z a-z 0-9 _ -), signed into the reply.")


class AdapterArtifactRequestView(SignedAdapterView):
    @_doc("Declare an artifact (timelapse, thumbnail, failure snapshot, log bundle) and get a presigned STAGING upload "
          "(signed)", "artifact", "artifact", code=201)
    def post(self, request):
        return Response(artifacts.request_upload(request.user, request.data), status=201)


class AdapterArtifactCompleteView(SignedAdapterView):
    @_doc("Finish an artifact upload: the server checks size and promotes it from staging (signed, idempotent)",
          response="artifact_done")
    def post(self, request, pk):
        return Response(artifacts.complete(request.user, pk))


class AdapterAccessCacheView(SignedAdapterView):
    @extend_schema(tags=[TAG], summary="Signed, expiring list of allowed NFC digests for offline decisions (signed)",
                   parameters=[_BINDING], responses={200: RESPONSES["access_cache"], **ERRORS})
    def get(self, request):
        binding_id = request.query_params.get("binding_id", "")
        from apps.devices.adapters.schema import UUID, errors
        if errors(UUID, binding_id):
            raise AdapterError("invalid_payload", "binding_id must be a uuid.")
        return Response(offline.build(request.user, binding_id))


class AdapterOfflineDecisionsView(SignedAdapterView):
    @_doc("Report decisions made offline; they become access-log rows, idempotent by operation_id (signed)", "offline",
          "offline")
    def post(self, request):
        return Response(offline.reconcile(request.user, request.data))


class AdapterConfigView(SignedAdapterView):
    @_doc("The latest pushed adapter config version (signed)", response="config")
    def get(self, request):
        return Response(config.fetch(request.user))


class AdapterConfigAckView(SignedAdapterView):
    @_doc("Acknowledge a config version as applied or rejected (signed, idempotent)", "config_ack", "config_ack")
    def post(self, request):
        return Response(config.acknowledge(request.user, request.data))


class AdapterTimeView(SignedAdapterView):
    @extend_schema(tags=[TAG], summary="Server time, Ed25519-signed; verify with the hello cache_keys (signed)",
                   parameters=[_NONCE], responses={200: RESPONSES["time"], **ERRORS})
    def get(self, request):
        return Response(config.server_time(request.user, request.query_params.get("nonce", "")))
