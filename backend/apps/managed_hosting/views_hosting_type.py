"""``GET/PUT admin/platform/spaces/<id>/hosting-type`` -- own space or hosted space (decision 236)."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.makerspaces.models import Makerspace
from apps.openapi_errors import errors

from . import hosting_type

TAGS = ["Managed hosting"]
CHOICES = [hosting_type.OWN, hosting_type.HOSTED]


class HostingTypeSerializer(serializers.Serializer):
    hosting_type = serializers.ChoiceField(choices=CHOICES, help_text="`own`: unlimited, no plan or billing. "
                                           "`hosted`: plans, limits, trials and hosting billing apply.")
    hosting_active = serializers.BooleanField(help_text="Hosting other makerspaces is on. Off: every space is own.")
    hosted = serializers.BooleanField(help_text="The type that is in force now.")


class HostingTypeUpdateSerializer(serializers.Serializer):
    hosting_type = serializers.ChoiceField(choices=CHOICES)


def _body(space):
    return {"hosting_type": hosting_type.stored_type(space), "hosting_active": hosting_type.hosting_active(),
            "hosted": hosting_type.is_hosted(space)}


class SpaceHostingTypeView(RecentReauthenticationMixin, APIView):
    """Readable always; the stored type is kept (never deleted) while hosting is off."""

    permission_classes = [IsActiveSuperAdmin]
    http_method_names = ["get", "put", "head", "options"]

    @extend_schema(tags=TAGS, summary="Read whether a space is your own or hosted",
                   responses={200: HostingTypeSerializer, **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        return Response(_body(get_object_or_404(Makerspace, pk=makerspace_id)))

    @extend_schema(tags=TAGS, summary="Mark a space as your own or hosted",
                   description="Superadmin only, recent re-authentication, audited "
                               "(`managed_hosting.hosting_type_changed`). Changing it deletes nothing: a plan, "
                               "overrides and invoices stay and apply again when the space is hosted.",
                   request=HostingTypeUpdateSerializer,
                   responses={200: HostingTypeSerializer, **errors(400, 401, 403, 404)})
    def put(self, request, makerspace_id):
        space = get_object_or_404(Makerspace, pk=makerspace_id)
        body = HostingTypeUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        hosting_type.set_type(request.user, space, body.validated_data["hosting_type"])
        return Response(_body(space))
