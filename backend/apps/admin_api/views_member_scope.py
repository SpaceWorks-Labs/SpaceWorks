from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.accounts.rbac_roles import additional_roles_prefetch
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_member_scope import (
    MemberMachineScopeSerializer, MemberMachineScopeWriteSerializer,
)
from apps.admin_api.views_roles import ERRORS, _makerspace
from apps.machines import member_scope_services as scopes
from apps.makerspaces.models import MakerspaceMembership


def _membership(actor, makerspace, membership_id):
    # Machine scopes hang off staff-track rows (one account per person).
    rows = rbac.scope_by_action(actor, rbac.Action.MANAGE_MAKERSPACE,
                               MakerspaceMembership.staff_tracks.all())
    return get_object_or_404(rows.select_related("assigned_role").prefetch_related(
        additional_roles_prefetch(),
    ), pk=membership_id, makerspace=makerspace)


def _payload(makerspace, membership):
    return {
        "membership_id": membership.pk,
        "scoping_applies": scopes.scoping_applies(membership),
        "machine_type_ids": scopes.current_scope(membership),
        "available_machine_types": [
            {"id": row.pk, "name": row.name, "slug": row.slug,
             "is_global": row.makerspace_id is None}
            for row in scopes.assignable_machine_types(makerspace)
        ],
    }


class MemberMachineScopeView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin memberships"],
                   description="Requires manage_makerspace in this makerspace.",
                   responses={200: MemberMachineScopeSerializer, **ERRORS})
    def get(self, request, makerspace_id, membership_id):
        space = _makerspace(request.user, makerspace_id)
        membership = _membership(request.user, space, membership_id)
        return Response(MemberMachineScopeSerializer(_payload(space, membership)).data)

    @extend_schema(tags=["Admin memberships"],
                   description="Requires manage_makerspace. Replaces the member's complete type scope; exempt or non-Machine-Manager memberships return 409.",
                   request=MemberMachineScopeWriteSerializer,
                   responses={200: MemberMachineScopeSerializer, **ERRORS})
    def put(self, request, makerspace_id, membership_id):
        space = _makerspace(request.user, makerspace_id)
        membership = _membership(request.user, space, membership_id)
        serializer = MemberMachineScopeWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        scopes.set_member_machine_scope(makerspace=space, membership=membership,
                                       actor=request.user, **serializer.validated_data)
        membership = _membership(request.user, space, membership_id)
        return Response(MemberMachineScopeSerializer(_payload(space, membership)).data)
