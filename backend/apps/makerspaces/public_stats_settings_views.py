"""Staff API for public stats: L17-authorized page settings and area-owned visibility."""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from . import public_stats_settings as group
from .models import Makerspace
from .public_stats_capabilities import capabilities
from .public_stats_settings_serializers import (
    PublicStatsSettingsErrorSerializer, PublicStatsSettingsInputError,
    PublicStatsSettingsResponseSerializer, PublicStatsSettingsSerializer,
    _KeyListField, _ChoiceSerializer, _MetricChoiceSerializer, _ChoicesSerializer,  # noqa: F401 -- old imports
)
from .servability import servable_queryset


def _payload(actor, space, config):
    allowed = capabilities(actor, space)
    return {"settings": config, "can_edit": allowed["settings"]["sections"]["editable"],
            "choices": group.choices(), "capabilities": allowed}


_ERRORS = {code: ErrorSerializer for code in (401, 403, 404, 423)}
_HEADERS = {"Cache-Control": "private, no-store"}
_WRITE_ERRORS = {400: PublicStatsSettingsErrorSerializer, **_ERRORS}


class PublicStatsSettingsView(APIView):
    permission_classes = [IsActiveStaff]

    def space(self, request, makerspace_id):
        rows = rbac.scope_by_visibility_or_action(request.user, rbac.Action.MANAGE_MAKERSPACE,
                                                  servable_queryset(Makerspace.objects.all()), field="pk")
        return get_object_or_404(rows, pk=makerspace_id)

    @extend_schema(tags=["Admin makerspaces"], summary="Read the public stats settings", request=None,
                   description="Staff read the configuration. capabilities reports the same per-field L17 "
                               "grant/lock decisions enforced on writes; available reports source module state.",
                   responses={200: PublicStatsSettingsResponseSerializer, **_ERRORS})
    def get(self, request, makerspace_id):
        space = self.space(request, makerspace_id)
        return Response(_payload(request.user, space, group.read_config(space)), headers=_HEADERS)

    def _save(self, request, makerspace_id, *, partial):
        space = self.space(request, makerspace_id)
        data = PublicStatsSettingsSerializer(data=request.data, partial=partial)
        if not data.is_valid():
            raise PublicStatsSettingsInputError(data.errors)
        saved = group.save_config(request.user, space, dict(data.validated_data))
        return Response(_payload(request.user, space, saved), headers=_HEADERS)

    @extend_schema(tags=["Admin makerspaces"], summary="Save the public stats settings",
                   description="Compatible full-group replacement. Every submitted page field and visibility key "
                               "is authorized through L17, including unchanged values. One refused key refuses "
                               "the whole request before any setting or audit entry is written.",
                   request=PublicStatsSettingsSerializer,
                   responses={200: PublicStatsSettingsResponseSerializer, **_WRITE_ERRORS})
    def put(self, request, makerspace_id):
        return self._save(request, makerspace_id, partial=False)

    @extend_schema(tags=["Admin makerspaces"], summary="Update selected public stats settings",
                   description="Partial update for delegated area managers. Send only changed allowed fields. "
                               "Page-wide settings remain Space-Manager-only; per-widget grants and locks "
                               "use the widget's owner_module. Module-off data remains hidden.",
                   request=PublicStatsSettingsSerializer,
                   responses={200: PublicStatsSettingsResponseSerializer, **_WRITE_ERRORS})
    def patch(self, request, makerspace_id):
        return self._save(request, makerspace_id, partial=True)
