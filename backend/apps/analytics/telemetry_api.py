from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.permissions import BasePermission, IsAuthenticated

from apps.accounts.models import User
from apps.openapi_errors import errors
from .api import _Scoped, _private
from .telemetry_serializers import TelemetryEnvelopeSerializer
from . import telemetry_service


class ActiveAccount(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return (getattr(user, "is_active", False)
                and getattr(user, "access_status", None) == User.AccessStatus.ACTIVE
                and not getattr(user, "must_change_password", False))


class TelemetryView(_Scoped):
    permission_classes = [IsAuthenticated, ActiveAccount]
    @extend_schema(tags=["Analytics"], summary="Read public web telemetry settings",
                   responses={200: TelemetryEnvelopeSerializer, **errors(401, 403, 404)})
    def get(self, request, **kwargs):
        scope = self.viewer(request, kwargs)
        return _private(Response({"config": telemetry_service.describe(scope)}))

    @extend_schema(tags=["Analytics"], summary="Replace public web telemetry settings",
                   request=TelemetryEnvelopeSerializer,
                   responses={200: TelemetryEnvelopeSerializer, **errors(400, 401, 403, 404)})
    def patch(self, request, **kwargs):
        scope = self.manager(request, kwargs)
        serializer = TelemetryEnvelopeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config = telemetry_service.update(scope, request.user, serializer.validated_data["config"])
        return _private(Response({"config": config}))
