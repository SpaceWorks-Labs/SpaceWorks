"""Per-space security settings: read, change and platform-lock (owner decisions #110c, #111).

Only the space's own Space Manager or a platform superadmin reads or changes them; locks
are superadmin-only. Every change needs recent re-authentication and is audited by the
service. Module managers and organization grants get 403.
"""

from django.utils.translation import gettext
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.platform_authority import is_platform_superadmin
from apps.accounts.reauthentication import require_recent_reauth
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_security_settings import (
    SecurityLockRequestSerializer, SecuritySettingsSerializer, SecuritySettingsUpdateSerializer,
)
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces import security_settings as service
from apps.makerspaces.models import Makerspace

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404)}
KEY = OpenApiParameter("key", str, OpenApiParameter.PATH, description="A registered security setting key.")


def _space(request, makerspace_id):
    space = get_object_or_404(Makerspace, pk=makerspace_id)
    if service.editor_via(request.user, space) is None:
        raise PermissionDenied(gettext("Only this space's Space Manager or a platform superadmin can view security settings."))
    return space


def _payload(request, space):
    via = service.editor_via(request.user, space)
    return {"makerspace_id": space.pk, "settings": service.effective(space), "can_edit": via is not None,
            "can_lock": is_platform_superadmin(request.user), "edited_as": via}


def _call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except DjangoValidationError as exc:
        if hasattr(exc, "status_code"):
            raise
        raise ValidationError({"detail": exc.messages[0], "code": getattr(exc, "code", None) or "invalid"}) from exc


def _no_store(response):
    response["Cache-Control"] = "private, no-store"
    return response


class SecuritySettingsView(APIView):
    permission_classes = [IsActiveStaff]
    serializer_class = SecuritySettingsSerializer

    @extend_schema(tags=["Security settings"], summary="Read a space's security settings",
                   description="The Space Manager of this space or a platform superadmin. Each row carries "
                               "its platform lock (floor and note) when one is set.",
                   responses={200: SecuritySettingsSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        return _no_store(Response(_payload(request, _space(request, makerspace_id))))

    @extend_schema(tags=["Security settings"], summary="Change security settings",
                   description="Recent re-authentication required (403 `recent_reauth_required`). A value "
                               "looser than a platform lock's floor is refused with 400 "
                               "`security_setting_locked`. Audited as `makerspace.security_setting_changed`.",
                   request=SecuritySettingsUpdateSerializer, responses={200: SecuritySettingsSerializer, **ERRORS})
    def patch(self, request, makerspace_id):
        space = _space(request, makerspace_id)
        require_recent_reauth(request)
        body = SecuritySettingsUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        space = _call(service.set_settings, request.user, space, body.validated_data["values"])
        return _no_store(Response(_payload(request, space)))


class SecuritySettingLockView(APIView):
    permission_classes = [IsActiveStaff]
    serializer_class = SecuritySettingsSerializer

    def _locked_space(self, request, makerspace_id):
        space = get_object_or_404(Makerspace, pk=makerspace_id)
        if not is_platform_superadmin(request.user):
            raise PermissionDenied(gettext("Only a platform superadmin can lock or unlock security settings."))
        require_recent_reauth(request)
        return space

    @extend_schema(tags=["Security settings"], summary="Lock a security setting at a floor",
                   description="Platform superadmin with recent re-authentication. The space cannot go below "
                               "the floor; a boolean lock forces the setting on, and a looser stored value is "
                               "raised to the floor. Audited as `makerspace.security_setting_locked`.",
                   parameters=[KEY], request=SecurityLockRequestSerializer,
                   responses={200: SecuritySettingsSerializer, **ERRORS})
    def put(self, request, makerspace_id, key):
        space = self._locked_space(request, makerspace_id)
        body = SecurityLockRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        _call(service.lock, request.user, space, key, body.validated_data["floor"], body.validated_data["note"])
        space.refresh_from_db()
        return _no_store(Response(_payload(request, space)))

    @extend_schema(tags=["Security settings"], summary="Remove a platform lock",
                   description="Platform superadmin with recent re-authentication. The stored value is kept. "
                               "Audited as `makerspace.security_setting_unlocked`.",
                   parameters=[KEY], request=None,
                   responses={200: SecuritySettingsSerializer, **ERRORS,
                              404: OpenApiResponse(ErrorSerializer, description="No such space or no lock.")})
    def delete(self, request, makerspace_id, key):
        space = self._locked_space(request, makerspace_id)
        if not _call(service.unlock, request.user, space, key):
            return Response({"detail": gettext("This setting is not locked."), "code": "not_locked"}, status=404)
        space.refresh_from_db()
        return _no_store(Response(_payload(request, space)))
