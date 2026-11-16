"""Decision 242(k): the staff Schedule route (read-only, per-role layers)."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.servability import servable_queryset
from apps.operations.schedule import LAYERS, build_schedule
from apps.operations.serializers_attention import AttentionLinkSerializer


class ScheduleEntrySerializer(serializers.Serializer):
    layer = serializers.ChoiceField(choices=LAYERS)
    area = serializers.CharField(help_text="Console area the entry belongs to; the Space Manager's view groups by it.")
    id = serializers.IntegerField()
    title = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    status = serializers.CharField()
    link = AttentionLinkSerializer()


class ScheduleGroupSerializer(serializers.Serializer):
    area = serializers.CharField()
    count = serializers.IntegerField()


class ScheduleSerializer(serializers.Serializer):
    class Meta:
        ref_name = "StaffSchedule"

    layers = serializers.ListField(child=serializers.ChoiceField(choices=LAYERS),
                                   help_text="The layers this caller may see.")
    entries = ScheduleEntrySerializer(many=True)
    groups = ScheduleGroupSerializer(many=True)

    def get_fields(self):
        fields = super().get_fields()
        fields["from"] = serializers.DateField()
        fields["to"] = serializers.DateField()
        return fields


class ScheduleView(APIView):
    permission_classes = [IsActiveStaff]
    http_method_names = ["get", "head", "options"]

    @extend_schema(
        tags=["Schedule"], summary="Staff schedule: bookings, events, machine jobs, maintenance, shifts",
        description=("Each role sees only its own layers (action + module/capability + rbac scope); the Space Manager "
                     "sees all, grouped by area. `start`/`end` are local ISO dates (default today..+14 days, max 62)."),
        parameters=[OpenApiParameter("start", str, required=False), OpenApiParameter("end", str, required=False),
                    OpenApiParameter("layers", str, required=False, description="Comma list of layer keys.")],
        responses={200: ScheduleSerializer, 401: OpenApiResponse(ErrorSerializer), 404: OpenApiResponse(ErrorSerializer)},
    )
    def get(self, request, makerspace_id):
        space = get_object_or_404(rbac.scope_by_makerspace(request.user, servable_queryset(), makerspace_field="id"),
                                  pk=makerspace_id)
        layers = [v for v in (request.query_params.get("layers") or "").split(",") if v in LAYERS]
        return Response(build_schedule(request.user, space, start=request.query_params.get("start"),
                                       end=request.query_params.get("end"), layers=layers))
