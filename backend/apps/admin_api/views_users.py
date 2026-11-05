from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from apps.admin_api.list_options import StableOrderingFilter
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_audit import (
    AuditLogFilterSerializer,
    AuditLogSerializer,
    apply_audit_filters,
)
from apps.admin_api.serializers_users import (
    StaffCreateSerializer,
    StaffMembershipSerializer,
)
from apps.audit.models import AuditLog
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.models import MakerspaceMembership

# Compatibility listings keep their existing non-manager role scope. Granting and
# changing staff roles go through the staff-roles API instead.
_SM_DELEGABLE_ROLES = (
    MakerspaceMembership.Role.INVENTORY_MANAGER,
    MakerspaceMembership.Role.MACHINE_MANAGER,
    MakerspaceMembership.Role.EVENT_MANAGER,
    MakerspaceMembership.Role.BOOKING_MANAGER,
    MakerspaceMembership.Role.HANDOVER,
    MakerspaceMembership.Role.TECHNICIAN,
    MakerspaceMembership.Role.SHOP_MANAGER,
)


@extend_schema(tags=["Admin users"], summary="List legacy staff memberships")
class StaffListCreateView(RecentReauthenticationMixin, generics.ListCreateAPIView):
    serializer_class = StaffMembershipSerializer
    permission_classes = [IsActiveStaff]

    def get_queryset(self):
        target_role = self.kwargs["role"]
        scope = rbac.makerspaces_for_action(self.request.user, rbac.Action.MANAGE_STAFF)
        queryset = MakerspaceMembership.staff_tracks.select_related("user", "makerspace").filter(
            role=target_role
        )
        if scope is rbac.ALL:
            return queryset.order_by("user__username")
        if target_role in _SM_DELEGABLE_ROLES:
            manage_scope = rbac.makerspaces_for_action(
                self.request.user,
                rbac.Action.MANAGE_MAKERSPACE,
            )
            if manage_scope is rbac.ALL:
                return queryset.order_by("user__username")
            return queryset.filter(makerspace_id__in=manage_scope).order_by(
                "user__username"
            )
        return queryset.none()

    @extend_schema(
        description="Retired writer. Grant staff roles through `admin/makerspaces/<id>/staff-roles/`.",
        deprecated=True,
        request=StaffCreateSerializer,
        responses={**{
            code: ErrorSerializer for code in (400, 401, 403, 404)
        }},
    )
    def create(self, request, *args, **kwargs):
        serializer = StaffCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not rbac.can(request.user, rbac.Action.MANAGE_MAKERSPACE, data["makerspace_id"]):
            raise PermissionDenied()
        raise ValidationError({"detail": "Grant staff roles through the staff-roles API."})


@extend_schema(tags=["Admin users"], summary="Revoke a staff row (legacy route)", responses={204: None})
class MembershipRevokeView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(responses={204: None, **{code: ErrorSerializer for code in (400, 401, 403, 404, 423, 503)}})
    def delete(self, request, pk):
        from django.shortcuts import get_object_or_404
        from apps.accounts.staff_account_lifecycle import revoke

        membership = get_object_or_404(rbac.scope_by_action(
            request.user, rbac.Action.MANAGE_MAKERSPACE, MakerspaceMembership.both_tracks()), pk=pk)
        if membership.track != MakerspaceMembership.Track.STAFF:
            raise ValidationError({"detail": "Use the community membership revocation workflow."})
        revoke(request.user, membership.makerspace_id, membership.pk,
               reason="Removed through legacy staff console")
        return Response(status=204)


class AuditLogPagination(PageNumberPagination):
    page_size = 24


@extend_schema(
    tags=["Admin users"],
    summary="List audit log entries",
    description=(
        "Tenant- and VIEW_AUDIT-scoped audit rows, newest first, 24 per page. `meta` is the "
        "presentation-catalogue projection, never the raw stored metadata; unknown or "
        "dynamically built actions expose `{}`. `start` is inclusive, `end` exclusive, and "
        "a start/end range may span at most 366 days. A valid but out-of-scope makerspace "
        "yields an empty page."
    ),
    parameters=[AuditLogFilterSerializer, OpenApiParameter("ordering", str, enum=["created_at", "-created_at", "action", "-action", "target_type", "-target_type"])],
    responses={200: AuditLogSerializer(many=True), **{code: ErrorSerializer for code in (400, 401, 403, 404)}},
)
class AuditLogListView(generics.ListAPIView):
    serializer_class = AuditLogSerializer
    permission_classes = [IsActiveStaff]
    pagination_class = AuditLogPagination
    filter_backends = [StableOrderingFilter]
    ordering_fields = ["created_at", "action", "target_type"]
    ordering = ["-created_at", "-pk"]

    def get_queryset(self):
        filters = AuditLogFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        queryset = AuditLog.objects.select_related("actor").order_by("-created_at", "-pk")
        # Tenant/action scope and archived spaces are applied BEFORE user filters.
        queryset = rbac.scope_by_action(self.request.user, rbac.Action.VIEW_AUDIT, queryset)
        archived = rbac.archived_makerspace_ids()
        if archived:
            queryset = queryset.exclude(makerspace_id__in=archived)
        return apply_audit_filters(queryset, filters.validated_data)
