"""Purge a switched-off capability's data from the web superadmin console (#190, parity with /control/).

The same irreversible step as /control/'s "Purge capability data", through the same
``capability_purge`` service: a preview of exactly what each capability would lose, the
capability key typed back, then a recent re-authentication, and the switch must already be
off. Audited in the space (``makerspace.capability_purge_started`` / ``..._purged``) by the
service; the space's source gate applies because the route names ``makerspace_id``.

Deliberately NOT capability-gated: a purge only ever acts on a switch that is OFF, so the
usual "off answers 404" rule would make this route unreachable exactly when it is needed.
"""

from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.openapi_errors import errors

from . import capability_purge
from .models import Makerspace

TAGS = ["Platform space keys"]


class CapabilityPlanSerializer(serializers.Serializer):
    key = serializers.CharField()
    summary = serializers.CharField()
    switched_on = serializers.BooleanField()
    counts = serializers.DictField(child=serializers.IntegerField(), help_text="Rows that would be deleted, by kind.")


class CapabilityPurgeSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=64)
    confirm = serializers.CharField(max_length=64, help_text="The capability key, typed back exactly.")


class CapabilityPurgeResultSerializer(serializers.Serializer):
    key = serializers.CharField()
    counts = serializers.DictField(child=serializers.IntegerField())


class CapabilityPurgeView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Preview what purging each switched-off capability of a space would delete",
                   responses={200: CapabilityPlanSerializer(many=True), **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        space = get_object_or_404(Makerspace, pk=makerspace_id)
        return Response(CapabilityPlanSerializer(capability_purge.purgeable_capabilities(space), many=True).data)

    @extend_schema(tags=TAGS, summary="Purge one switched-off capability's data (key typed back; irreversible)",
                   request=CapabilityPurgeSerializer,
                   responses={200: CapabilityPurgeResultSerializer,
                              **errors(400, 401, 403, 404, 409, 423, e409="Still switched on, or not purgeable (`purge_refused`).")})
    def post(self, request, makerspace_id):
        space = get_object_or_404(Makerspace, pk=makerspace_id)
        body = CapabilityPurgeSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        key = body.validated_data["key"]
        if body.validated_data["confirm"].strip() != key:
            return Response({"code": "confirm_mismatch", "confirm": ["Type the capability key exactly to confirm."]},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            counts = capability_purge.purge_capability(space, key, request.user)
        except ValidationError as exc:
            return Response({"code": "purge_refused", "detail": "; ".join(exc.messages)}, status=status.HTTP_409_CONFLICT)
        return Response({"key": key, "counts": counts})
