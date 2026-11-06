"""One space's keys in the web superadmin console (#190 follow-up, parity with /control/ Keys).

The per-space operations of the /control/ Keys page and ``manage.py backup_keys``: data-key
rotation, emergency re-key, search-key rotation, browser-key rotation, and re-encrypting or
purging this space's own archives on a retired backup key. Platform and server backup key
rotation stays on the server.

Superadmin only. Every write needs recent re-authentication AND the space's slug typed
back, passes the space's source gate (the route names ``makerspace_id``), and runs through
the same services /control/ calls, which audit in the space. Long work runs as Celery jobs
whose progress this GET returns.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.makerspaces.models import Makerspace
from apps.openapi_errors import errors

from .serializers_space_keys import (
    SpaceArchiveJobQueuedSerializer, SpaceArchiveKeyActionSerializer, SpaceKeyActionSerializer, SpaceKeyStateSerializer,
    require_typed_slug,
)

TAGS = ["Platform space keys"]
_WRITE_ERRORS = errors(400, 401, 403, 404, 409, 423, e409="Refused in the current state (typed `code`).")


def _space(makerspace_id):
    return get_object_or_404(Makerspace, pk=makerspace_id)


def _refused(exc):
    """A service's Django ValidationError as the typed 409 the console shows."""
    return Response({"code": "key_action_refused", "detail": "; ".join(exc.messages)}, status=status.HTTP_409_CONFLICT)


class SpaceKeysView(APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="A space's key versions, key jobs with progress, and archives on a retired key",
                   responses={200: SpaceKeyStateSerializer, **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        from .space_key_state import state
        return Response(SpaceKeyStateSerializer(state(_space(makerspace_id))).data)


class SpaceKeyRotateView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Rotate one of a space's keys (the slug typed back to confirm)",
                   request=SpaceKeyActionSerializer,
                   responses={202: SpaceKeyStateSerializer, **_WRITE_ERRORS})
    def post(self, request, makerspace_id):
        from django.core.exceptions import ValidationError
        from . import publishable_keys, rotation
        from .space_key_state import state
        space = _space(makerspace_id)
        body = SpaceKeyActionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        require_typed_slug(space, body.validated_data["confirm_slug"])
        action = body.validated_data["action"]
        try:
            if action in {"rotate_dek", "emergency_rekey"}:
                rotation.start_dek_rotation(request.user, space, emergency=action == "emergency_rekey")
            elif action == "rotate_search_key":
                rotation.start_search_key_rotation(request.user, space)
            else:
                publishable_keys.rotate_publishable_key(request.user, space)
        except ValidationError as exc:
            return _refused(exc)
        return Response(SpaceKeyStateSerializer(state(space)).data, status=status.HTTP_202_ACCEPTED)


class SpaceArchiveKeyView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Re-encrypt or purge one of a space's archives on a retired backup key",
                   request=SpaceArchiveKeyActionSerializer,
                   responses={202: SpaceArchiveJobQueuedSerializer, **_WRITE_ERRORS})
    def post(self, request, makerspace_id, archive_id):
        from apps.backup.space_archive_keys import job_state, queue
        space = _space(makerspace_id)
        body = SpaceArchiveKeyActionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        require_typed_slug(space, body.validated_data["confirm_slug"])
        row = queue(request.user, space, archive_id, body.validated_data["action"])
        return Response({"archive_id": str(row.pk), "job": job_state(row.pk)}, status=status.HTTP_202_ACCEPTED)
