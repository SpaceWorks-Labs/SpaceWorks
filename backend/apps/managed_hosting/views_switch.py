"""The superadmin's "Hosting other makerspaces" switch (#234).

Unlike the other managed-hosting routes this one answers while the feature is OFF, because it
is the control that turns it on. ``MANAGED_PLANS_ENABLED`` (legacy env preset), when set,
forces the answer and the switch is read-only. Turning it off hides the features and never
deletes plans, invoices or requests.
"""

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.audit import services as audit
from apps.openapi_errors import errors

from .availability import hosting_enabled, hosting_switch_forced
from .models import PlatformHostingBillingSettings
from django.utils.translation import gettext


class HostingSwitchSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    forced_by_environment = serializers.BooleanField(read_only=True)


def _payload():
    return {"enabled": hosting_enabled(), "forced_by_environment": hosting_switch_forced()}


class HostingSwitchView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=["Managed hosting"], summary="Read the Hosting-other-makerspaces switch",
                   responses={200: HostingSwitchSerializer, **errors(401, 403)})
    def get(self, request):
        return Response(_payload())

    @extend_schema(tags=["Managed hosting"], summary="Turn Hosting other makerspaces on or off",
                   request=HostingSwitchSerializer,
                   responses={200: HostingSwitchSerializer, **errors(400, 401, 403, 409)})
    def put(self, request):
        body = HostingSwitchSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        if hosting_switch_forced():
            raise serializers.ValidationError(
                {"enabled": gettext("This install sets MANAGED_PLANS_ENABLED, which overrides the switch.")})
        with transaction.atomic():
            row = PlatformHostingBillingSettings.objects.select_for_update().get(pk=PlatformHostingBillingSettings.load().pk)
            before = row.hosting_enabled
            row.hosting_enabled = body.validated_data["enabled"]
            row.updated_by = request.user
            row.save()
            audit.record(request.user, "managed_hosting.hosting_switch_changed", makerspace=None, target=row,
                         meta={"from": before, "to": row.hosting_enabled})
        return Response(_payload())
