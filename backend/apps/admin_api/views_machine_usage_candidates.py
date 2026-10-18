"""A scoped member picker for staff who may log this machine's usage."""

from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.machine_access import resolve_machine
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_machine_candidates import OperatorCandidateSerializer
from apps.machines import access
from apps.makerspaces.guards import require_module
from apps.makerspaces.models import MakerspaceMembership
from apps.openapi_errors import errors


class MachineUsageCandidatesView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Admin machines"], summary="Find active members for manual usage attribution",
        parameters=[OpenApiParameter("q", str), OpenApiParameter("page", int)],
        responses={200: inline_serializer(name="MachineUsageCandidatesPage", fields={
            "count": serializers.IntegerField(), "next": serializers.URLField(allow_null=True),
            "previous": serializers.URLField(allow_null=True), "results": OperatorCandidateSerializer(many=True),
        }), **errors(400, 401, 403, 404)},
    )
    def get(self, request, pk):
        machine = resolve_machine(request.user, pk)
        require_module(machine.makerspace_id, "machines")
        if not access.can_operate_machine(request.user, machine):
            raise PermissionDenied()
        query = rbac.scope_by_makerspace(request.user, MakerspaceMembership.objects.all()).filter(
            makerspace_id=machine.makerspace_id, status="active", user__is_active=True,
            user__access_status="active", user__is_tenant_dump_stub=False,
            user__account_kind="member", user__retired_at__isnull=True,
            user__deletion_requested_at__isnull=True,
        )
        term = request.query_params.get("q", "").strip()[:100]
        if term:
            query = query.filter(Q(user__username__icontains=term) | Q(user__display_name__icontains=term))
        paginator = PageNumberPagination()
        paginator.page_size = 24
        page = paginator.paginate_queryset(query.select_related("user").order_by("user__username", "pk"), request)
        return paginator.get_paginated_response(OperatorCandidateSerializer(page, many=True).data)
