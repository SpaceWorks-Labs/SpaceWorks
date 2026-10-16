from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.rbac_roles import additional_roles_prefetch
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_memberships import (
    MembershipCreateSerializer,
    MembershipListSerializer,
    MembershipRoleAssignSerializer,
)
from apps.admin_api.serializers_payment_summary import scoped_payment_context
from apps.admin_api.serializers_role_sets import ROLE_SET_VALIDATION_ERROR, resolve_role_set
from apps.admin_api.services_staff import attach_staff_membership
from apps.admin_api.views_roles import ERRORS, _makerspace
from apps.admin_api.views_member_memberships import _makerspace as member_makerspace
from apps.audit import services as audit
from apps.makerspaces import role_services
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.payments.models import Payment


class MembershipListCreateView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Admin memberships"],
        description="Requires manage_members in this makerspace. Staff creation and role administration require manage_makerspace.",
        responses={200: MembershipListSerializer(many=True), **ERRORS},
    )
    def get(self, request, makerspace_id):
        makerspace = member_makerspace(request.user, makerspace_id)
        memberships = (
            MakerspaceMembership.objects.filter(makerspace=makerspace)
            .select_related("user", "makerspace", "assigned_role").prefetch_related(additional_roles_prefetch())
            .order_by("user__username")
        )
        memberships = list(memberships)
        context = scoped_payment_context(
            request.user,
            rbac.Action.VIEW_FINANCE,
            Payment.SubjectType.MAKERSPACE_MEMBERSHIP,
            [membership.pk for membership in memberships],
        )
        return Response(
            MembershipListSerializer(
                memberships,
                many=True,
                context=context,
            ).data
        )

    @extend_schema(
        tags=["Admin memberships"],
        description="Requires manage_makerspace. Create or reattach staff with exactly one of role_id or role_ids (the complete set). Space Manager and Member are exclusive; unknown or foreign IDs return 404.",
        request=MembershipCreateSerializer,
        responses={201: MembershipListSerializer, **ERRORS, 400: ROLE_SET_VALIDATION_ERROR},
    )
    def post(self, request, makerspace_id):
        makerspace = _makerspace(request.user, makerspace_id)
        serializer = MembershipCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        roles = resolve_role_set(makerspace, data)
        with transaction.atomic():
            # Authority checks lock the actor membership; acquire its makerspace
            # first, matching assignment and lifecycle writers' lock order.
            makerspace = Makerspace.objects.select_for_update().get(pk=makerspace.pk)
            role_services.can_assign_roles(request.user, makerspace, roles)
            membership, created, is_break_glass = attach_staff_membership(
                actor=request.user,
                makerspace=makerspace,
                roles=roles,
                username=data["username"],
                email=data.get("email", ""),
                first_name=data.get("first_name", ""),
                last_name=data.get("last_name", ""),
                password=data.get("password", ""),
            )
            audit.record(
                request.user,
                (
                    "superadmin.break_glass_space_manager_created"
                    if is_break_glass
                    else "staff.created" if created else "staff.membership_updated"
                ),
                makerspace=makerspace,
                target=membership.user,
                meta={"role_ids": [role.pk for role in roles],
                      "role_slugs": [role.slug for role in roles]},
            )
        membership = (
            MakerspaceMembership.objects.select_related("user", "makerspace", "assigned_role").prefetch_related(additional_roles_prefetch())
            .get(pk=membership.pk)
        )
        context = scoped_payment_context(
            request.user,
            rbac.Action.VIEW_FINANCE,
            Payment.SubjectType.MAKERSPACE_MEMBERSHIP,
            [membership.pk],
        )
        return Response(
            MembershipListSerializer(membership, context=context).data,
            status=status.HTTP_201_CREATED,
        )


class MembershipRoleAssignView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Admin memberships"],
        description="Requires manage_makerspace. Replace the complete role set using exactly one of role_id or role_ids. Duplicate IDs are ignored; Space Manager and Member are exclusive. Unknown or foreign IDs return 404.",
        request=MembershipRoleAssignSerializer,
        responses={200: MembershipListSerializer, **ERRORS, 400: ROLE_SET_VALIDATION_ERROR},
    )
    def patch(self, request, makerspace_id, membership_id):
        makerspace = _makerspace(request.user, makerspace_id)
        membership = get_object_or_404(
            MakerspaceMembership.objects.filter(makerspace=makerspace), pk=membership_id
        )
        serializer = MembershipRoleAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        roles = resolve_role_set(makerspace, serializer.validated_data)
        membership = role_services.set_membership_roles(
            makerspace=makerspace,
            actor=request.user,
            membership=membership,
            roles=roles,
        )
        membership = (
            MakerspaceMembership.objects.select_related("user", "makerspace", "assigned_role").prefetch_related(additional_roles_prefetch())
            .get(pk=membership.pk)
        )
        context = scoped_payment_context(
            request.user,
            rbac.Action.VIEW_FINANCE,
            Payment.SubjectType.MAKERSPACE_MEMBERSHIP,
            [membership.pk],
        )
        return Response(MembershipListSerializer(membership, context=context).data)
