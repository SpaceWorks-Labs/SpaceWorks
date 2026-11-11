"""Decision 259 (MC4): upcoming induction events per machine type, readable from the Machines console.

The Event drawer needs `manage_events`; a Machine Manager sees the induction events for the certification types
they may grant (`induction._may_grant`, the same authority as every other certification grant) here instead.
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.machines import induction
from apps.machines.models import EventInductionLink
from apps.makerspaces.models import Makerspace
from apps.openapi_errors import errors

LIMIT = 50


class UpcomingInductionSerializer(serializers.Serializer):
    link_id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    title = serializers.CharField()
    starts_at = serializers.DateTimeField()
    certification_type = serializers.IntegerField()
    certification_type_name = serializers.CharField()
    machine_type_id = serializers.IntegerField()


class UpcomingInductionsView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin machine induction"], summary="Upcoming induction events per machine type",
                   parameters=[OpenApiParameter("machine_type", int, required=False)],
                   responses={200: UpcomingInductionSerializer(many=True), **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        space = get_object_or_404(rbac.scope_by_visibility_or_action(
            request.user, rbac.Action.MANAGE_MACHINES, Makerspace.objects.all(), field="id"), pk=makerspace_id)
        induction.require_induction(space)
        if not rbac.can(request.user, rbac.Action.MANAGE_MACHINES, space.pk):
            raise PermissionDenied()
        rows = EventInductionLink.objects.filter(
            makerspace=space, event__ends_at__gte=timezone.now(),
        ).exclude(event__status="cancelled").select_related("event", "certification_type").order_by("event__starts_at")
        wanted = request.query_params.get("machine_type")
        if wanted and wanted.isdecimal():
            rows = rows.filter(certification_type__machine_type_id=int(wanted))
        out = [{"link_id": row.pk, "event_id": row.event_id, "title": row.event.title, "starts_at": row.event.starts_at,
                "certification_type": row.certification_type_id, "certification_type_name": row.certification_type.name,
                "machine_type_id": row.certification_type.machine_type_id}
               for row in rows if induction._may_grant(request.user, row.certification_type)]
        return Response(UpcomingInductionSerializer(out[:LIMIT], many=True).data)
