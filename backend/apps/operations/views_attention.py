"""Decision 242(i)(j): the per-area "Waiting on me" counters as their own route (refresh and area filter)."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.servability import servable_queryset
from apps.operations.dashboard_attention import AREAS, build_attention
from apps.operations.serializers_attention import AttentionSerializer


class AttentionView(APIView):
    permission_classes = [IsActiveStaff]
    http_method_names = ["get", "head", "options"]

    @extend_schema(
        tags=["Dashboard"], summary="What is waiting on me, per area",
        description=("Counts only, each built from the caller's own actions with rbac scoping (decision 242). Space "
                     "Managers see every area; area managers, the Shop Manager and Technicians see their own."),
        parameters=[OpenApiParameter("area", str, required=False, enum=[key for key, _ in AREAS])],
        responses={200: AttentionSerializer, 401: OpenApiResponse(ErrorSerializer), 404: OpenApiResponse(ErrorSerializer)},
    )
    def get(self, request, makerspace_id):
        space = get_object_or_404(rbac.scope_by_makerspace(request.user, servable_queryset(), makerspace_field="id"),
                                  pk=makerspace_id)
        area = request.query_params.get("area")
        return Response(build_attention(request.user, space, area=area if area in dict(AREAS) else None))
