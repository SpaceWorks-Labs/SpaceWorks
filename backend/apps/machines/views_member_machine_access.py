"""'My machine access' (decision 319): the member's own grants and the machines open to every member.

Own rows only (never other members, never the staff note), in the member's own space, behind the
`machines` module. Replaces the retired own-certifications list.
"""
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.makerspaces.guards import require_module
from apps.makerspaces.member_activity_service import active_membership
from apps.openapi_errors import errors

from .models import Machine, MachineAccessGrant


class MemberAccessGrantSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    machine_id = serializers.IntegerField(allow_null=True)
    machine_name = serializers.CharField(allow_null=True)
    machine_type_name = serializers.CharField(allow_null=True)
    granted_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField(allow_null=True)
    status = serializers.ChoiceField(choices=["live", "expired"])


class OpenMachineSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class MemberMachineAccessSerializer(serializers.Serializer):
    grants = MemberAccessGrantSerializer(many=True)
    open_machines = OpenMachineSerializer(many=True)


class MemberMachineAccessView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Member machines"], summary="Your machine access", request=None,
                   responses={200: MemberMachineAccessSerializer, **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        membership = active_membership(request.user, makerspace_id)
        if membership is None:
            raise PermissionDenied()
        require_module(membership.makerspace, "machines")
        now = timezone.now()
        rows = MachineAccessGrant.objects.filter(
            makerspace=membership.makerspace, member=request.user, revoked_at__isnull=True,
        ).select_related("machine", "machine_type").order_by("-granted_at", "-pk")
        grants = [{"id": row.pk, "machine_id": row.machine_id, "machine_name": row.machine.name if row.machine_id else None,
                   "machine_type_name": row.machine_type.name if row.machine_type_id else None,
                   "granted_at": row.granted_at, "expires_at": row.expires_at,
                   "status": "live" if row.is_live(now) else "expired"} for row in rows]
        open_machines = Machine.objects.filter(makerspace=membership.makerspace, is_active=True, is_public=True,
                                               open_to_all_members=True).order_by("name", "pk")
        return Response({"grants": grants, "open_machines": [{"id": m.pk, "name": m.name} for m in open_machines]})
