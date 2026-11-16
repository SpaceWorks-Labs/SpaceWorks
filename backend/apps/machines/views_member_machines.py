"""Member-facing machine list with ids (0.12.0, UI lane U2).

The anonymous public list is a deliberate id-less allowlist. A signed-in active member needs the
machine id to build the "Supervise" and "Use" links, so this list adds `id` for members only and
otherwise mirrors the public projection (published, active machines of the member's own space).
"""
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.makerspaces.guards import require_module
from apps.makerspaces.member_activity_service import active_membership
from apps.openapi_errors import errors

from .models import Machine
from .serializers_public_machines import PublicMachineSerializer


class MemberMachineSerializer(PublicMachineSerializer):
    id = serializers.IntegerField(read_only=True)


class MemberMachinePageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = MemberMachineSerializer(many=True)


class MemberMachineListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Member machines"], summary="List the machines of your makerspace, with ids",
                   parameters=[OpenApiParameter("page", int, OpenApiParameter.QUERY, description="Page number (24 rows per page).")],
                   request=None, responses={200: MemberMachinePageSerializer, **errors(400, 401, 403, 404)})
    def get(self, request, makerspace_id):
        membership = active_membership(request.user, makerspace_id)
        if membership is None:
            raise PermissionDenied()
        require_module(membership.makerspace, "machines")
        rows = Machine.objects.select_related("machine_type").filter(
            makerspace=membership.makerspace, is_public=True, is_active=True).order_by("name", "pk")
        paginator = PageNumberPagination()
        paginator.page_size = 24
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(MemberMachineSerializer(page, many=True).data)
