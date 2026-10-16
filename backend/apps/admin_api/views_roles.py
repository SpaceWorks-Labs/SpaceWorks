from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_roles import (
    RoleSerializer,
    role_queryset,
)
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.models import Makerspace
from apps.makerspaces.role_catalog import BUILTIN_ROLE_SLUGS
from apps.makerspaces.servability import servable_queryset


ERRORS = {400: ErrorSerializer, 401: ErrorSerializer, 403: ErrorSerializer, 404: ErrorSerializer, 409: OpenApiResponse(ErrorSerializer)}

def _makerspace(actor, makerspace_id):
    makerspace = get_object_or_404(
        rbac.scope_by_visibility_or_action(
            actor,
            rbac.Action.MANAGE_MAKERSPACE,
            Makerspace.objects.all(),
            field="id",
        ),
        pk=makerspace_id,
    )
    if not rbac.can(actor, rbac.Action.MANAGE_MAKERSPACE, makerspace.pk):
        raise PermissionDenied()
    return makerspace


class RoleListCreateView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin roles"], description="Requires manage_makerspace for all roles, or manage_members for action-less community roles only.", responses={200: RoleSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        spaces = servable_queryset()
        visible = rbac.scope_by_visibility_or_action(
            request.user, rbac.Action.MANAGE_MAKERSPACE, spaces, field="id",
        ) | rbac.scope_by_action(
            request.user, rbac.Action.MANAGE_MEMBERS, spaces, field="id",
        )
        makerspace = get_object_or_404(visible, pk=makerspace_id)
        if rbac.can(request.user, rbac.Action.MANAGE_MAKERSPACE, makerspace.pk):
            rows = role_queryset().filter(makerspace=makerspace)
        else:
            if not rbac.can(request.user, rbac.Action.MANAGE_MEMBERS, makerspace.pk):
                raise PermissionDenied()
            rows = role_queryset().filter(makerspace=makerspace, granted_actions=[])
        order = {slug: index for index, slug in enumerate(BUILTIN_ROLE_SLUGS)}
        rows = sorted(rows.filter(slug__in=BUILTIN_ROLE_SLUGS), key=lambda role: order[role.slug])
        return Response(RoleSerializer(rows, many=True).data)
