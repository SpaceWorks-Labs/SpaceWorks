from apps.accounts.staff_identity import person_q
from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter, PolymorphicProxySerializer
from apps.admin_api.list_options import LIST_PARAMETERS, ORDER_PAGE_PARAMETERS, choice_filter, identity_filter, order_list
from apps.admin_api.serializers_member_list import MembershipListResponseSerializer, MembershipRequestListResponseSerializer
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.rbac_roles import additional_roles_prefetch
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_member_memberships import (AdminMembershipSerializer, ApproveRequestSerializer,
    InvitationSerializer, MembershipRequestSerializer, RevokeSerializer)
from apps.admin_api.serializers_payment_summary import scoped_payment_context
from apps.admin_api.serializers_role_sets import (
    ROLE_SET_VALIDATION_ERROR, RoleSetInputSerializer, resolve_role_set,
)
from apps.admin_api.views_roles import ERRORS as ROLE_ERRORS
from apps.makerspaces import membership_services, waiver_services
from apps.makerspaces.member_unit_scope import (
    narrow_by_unit_lookup, require_member_in_scope, require_request_in_scope,
)
from apps.makerspaces.guards import require_module
from apps.makerspaces.membership_gating import require_module_for_request, staff_invitation_q
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole, MakerspaceWaiver, MembershipPlan, MembershipRequest
from apps.makerspaces.serializers_memberships import MemberWaiverResponseSerializer, WaiverPublishSerializer
from apps.makerspaces.servability import servable_queryset
from apps.payments.models import Payment

ERRORS = {**ROLE_ERRORS, 423: ROLE_ERRORS[400], 503: ROLE_ERRORS[400]}


class MembershipPagination(PageNumberPagination):
    page_size = 24


def _makerspace(actor, makerspace_id, action=rbac.Action.MANAGE_MEMBERS):
    queryset = rbac.scope_by_visibility_or_action(
        actor, action, servable_queryset(), field="id"
    )
    makerspace = get_object_or_404(queryset, pk=makerspace_id)
    if not rbac.can(actor, action, makerspace.id):
        raise PermissionDenied()
    return makerspace


def _role(makerspace, role_id):
    return get_object_or_404(MakerspaceRole.objects.filter(makerspace=makerspace), pk=role_id)


def _membership_context(actor, membership, **extra):
    return {
        "actor": actor,
        **extra,
        **scoped_payment_context(
            actor,
            rbac.Action.VIEW_FINANCE,
            Payment.SubjectType.MAKERSPACE_MEMBERSHIP,
            [membership.pk],
        ),
    }


def _admission_context(actor, rows):
    return {"actor": actor, **scoped_payment_context(
        actor, rbac.Action.VIEW_FINANCE, Payment.SubjectType.MEMBERSHIP_REQUEST,
        [row.pk for row in rows],
    )}


def _more_roster_filters(queryset, params):
    """Decision 242 (PE4): name/email search, role, account standing and join-date filters."""
    from django.db.models import Q
    if term := (params.get("q") or "").strip():
        queryset = queryset.filter(
            Q(user__username__icontains=term) | Q(user__first_name__icontains=term)
            | Q(user__last_name__icontains=term) | Q(user__email__icontains=term))
    if str(params.get("role", "")).isdigit():
        queryset = queryset.filter(Q(assigned_role_id=int(params["role"])) | Q(additional_roles__role_id=int(params["role"]))).distinct()
    if params.get("standing") in ("active", "restricted", "suspended"):
        queryset = queryset.filter(user__access_status=params["standing"])
    for key, lookup in (("joined_after", "created_at__date__gte"), ("joined_before", "created_at__date__lte")):
        if params.get(key):
            try:
                from datetime import date
                queryset = queryset.filter(**{lookup: date.fromisoformat(params[key])})
            except ValueError:
                pass
    return queryset


class AdminMembershipRosterView(APIView):
    permission_classes = [IsActiveStaff]
    pagination_class = MembershipPagination

    @extend_schema(description="Requires manage_members in this makerspace; staff role administration and waiver publishing require manage_makerspace.", tags=["Admin memberships"], parameters=[*LIST_PARAMETERS, OpenApiParameter("makerspace_id", int, required=True), OpenApiParameter("status", str), OpenApiParameter("id", int, description="Select one membership within the authorized roster."),
        # Decision 242 (PE4): `q` also matches name and email; role, standing and join-date filters.
        OpenApiParameter("role", int), OpenApiParameter("standing", str), OpenApiParameter("joined_after", str), OpenApiParameter("joined_before", str),
        # Decision 248: plan id, and true/false flags for staff, verified, minor, volunteer; waiver_needed=true.
        OpenApiParameter("plan", int), OpenApiParameter("staff", str), OpenApiParameter("verified", str), OpenApiParameter("minor", str), OpenApiParameter("volunteer", str), OpenApiParameter("waiver_needed", str),
        # Parity O-B2: the shared register filter contract.
        OpenApiParameter("title", int), OpenApiParameter("unit", int, description="A unit id; includes the units beneath it."), OpenApiParameter("chip", str, description="active | expiring | grace | lapsed | upcoming | no_term | approval | payment | changes")], responses={200: MembershipListResponseSerializer, **ERRORS})
    def get(self, request):
        makerspace = _makerspace(request.user, request.query_params.get("makerspace_id"))
        active = rbac.scope_by_action(request.user, rbac.Action.MANAGE_MEMBERS, MakerspaceWaiver.objects.filter(makerspace=makerspace, is_active=True)).first()
        queryset = MakerspaceMembership.objects.filter(person_q("user__"), makerspace=makerspace).select_related("user", "assigned_role").prefetch_related(additional_roles_prefetch()).order_by("user__username")
        queryset = rbac.scope_by_action(request.user, rbac.Action.MANAGE_MEMBERS, queryset)
        selected_id = identity_filter(request.query_params)
        if selected_id is not None:
            queryset = queryset.filter(pk=selected_id)
        # Parity O-B2: the one filter contract shared with the register and the card-job resolver; it also applies
        # the actor's unit scope (O-B1), so no filter can widen what a scoped lead sees.
        from apps.admin_api.member_register_filters import apply_member_filters, from_query
        queryset = apply_member_filters(queryset, from_query(request.query_params), makerspace, actor=request.user)
        selected_status = choice_filter(request.query_params, "status", dict(MakerspaceMembership._meta.get_field("status").choices))
        if selected_status:
            queryset = queryset.filter(status=selected_status)
        queryset = order_list(queryset, request.query_params, {"user__username", "status", "created_at"}, "user__username")
        pager = self.pagination_class()
        page = pager.paginate_queryset(queryset, request)
        context = {
            "actor": request.user,
            # Resolved once for the whole roster. The waiver predicates take it as an
            # explicit argument precisely so a per-row lookup cannot become an N+1.
            "active_waiver": active,
            **scoped_payment_context(
                request.user,
                rbac.Action.VIEW_FINANCE,
                Payment.SubjectType.MAKERSPACE_MEMBERSHIP,
                [membership.pk for membership in page],
            ),
        }
        return pager.get_paginated_response(AdminMembershipSerializer(
            page, many=True, context=context
        ).data)


class AdminMembershipRequestListView(APIView):
    permission_classes = [IsActiveStaff]
    pagination_class = MembershipPagination

    @extend_schema(description="Requires manage_members in this makerspace; staff role administration and waiver publishing require manage_makerspace.", tags=["Admin memberships"], parameters=[*ORDER_PAGE_PARAMETERS, OpenApiParameter("makerspace_id", int, required=True), OpenApiParameter("state", str)], responses={200: MembershipRequestListResponseSerializer, **ERRORS})
    def get(self, request):
        makerspace = _makerspace(request.user, request.query_params.get("makerspace_id"))
        queryset = MembershipRequest.objects.filter(makerspace=makerspace).select_related("user", "assigned_role", "admission_payment").prefetch_related("vouches__voucher")
        queryset = rbac.scope_by_action(request.user, rbac.Action.MANAGE_MEMBERS, queryset)
        queryset = narrow_by_unit_lookup(queryset, request.user, makerspace.pk, "unit_choice__unit__path",
                                         rbac.Action.MANAGE_MEMBERS)  # parity O-B1: unit-scoped staff
        if not module_enabled(makerspace, "membership"):
            # Staff must not be shown community join requests they have no enabled surface
            # to action -- but a STAFF invitation is core RBAC business and must stay
            # visible, or one issued with the module off could never be found again.
            queryset = queryset.filter(staff_invitation_q())
        selected_state = choice_filter(request.query_params, "state", MembershipRequest.State.values)
        if selected_state:
            queryset = queryset.filter(state=selected_state)
        pager = self.pagination_class()
        page = pager.paginate_queryset(order_list(queryset, request.query_params, {"created_at", "state"}, "-created_at"), request)
        return pager.get_paginated_response(MembershipRequestSerializer(page, many=True, context=_admission_context(request.user, page)).data)


class AdminInvitationView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(description="Requires manage_members in this makerspace; staff role administration and waiver publishing require manage_makerspace.", tags=["Admin memberships"], request=InvitationSerializer, responses={201: MembershipRequestSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        makerspace = _makerspace(request.user, makerspace_id)
        serializer = InvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = membership_services.invite_membership(request.user, makerspace, serializer.validated_data["invite_email"], _role(makerspace, serializer.validated_data["role_id"]))
        return Response(MembershipRequestSerializer(item, context=_admission_context(request.user, [item])).data, status=status.HTTP_201_CREATED)


class AdminRequestApproveView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(description="Requires manage_members. Returns an admission request when payment is due, otherwise the activated membership.", tags=["Admin memberships"], request=ApproveRequestSerializer, responses={200: PolymorphicProxySerializer(component_name="MembershipApprovalOutcome", serializers=[AdminMembershipSerializer, MembershipRequestSerializer], resource_type_field_name=None), **ERRORS})
    def post(self, request, pk):
        item = get_object_or_404(rbac.scope_by_visibility_or_action(request.user, rbac.Action.MANAGE_MEMBERS, MembershipRequest.objects.select_related("makerspace")), pk=pk)
        require_request_in_scope(request.user, item, rbac.Action.MANAGE_MEMBERS)  # parity O-B1
        makerspace = _makerspace(request.user, item.makerspace_id)
        serializer = ApproveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = _role(makerspace, serializer.validated_data["role_id"])
        require_module_for_request(makerspace, item, outcome_role=role)
        plan = None
        if serializer.validated_data.get("plan_id") is not None:
            # Plans are the module's own surface, whatever the request is.
            require_module(makerspace, "membership")
            plan = get_object_or_404(MembershipPlan.objects.filter(makerspace=makerspace), pk=serializer.validated_data["plan_id"])
        membership = membership_services.approve_request(request.user, item, role, plan=plan)
        if isinstance(membership, MembershipRequest):
            return Response(MembershipRequestSerializer(membership, context=_admission_context(request.user, [membership])).data)
        membership = MakerspaceMembership.objects.select_related(
            "user", "assigned_role"
        ).get(pk=membership.pk)
        return Response(
            AdminMembershipSerializer(
                membership,
                context=_membership_context(request.user, membership),
            ).data
        )


class AdminRequestRevokeView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(description="Requires manage_members in this makerspace; staff role administration and waiver publishing require manage_makerspace.", tags=["Admin memberships"], request=RevokeSerializer, responses={200: MembershipRequestSerializer, **ERRORS})
    def post(self, request, pk):
        item = get_object_or_404(rbac.scope_by_visibility_or_action(request.user, rbac.Action.MANAGE_MEMBERS, MembershipRequest.objects.select_related("makerspace")), pk=pk)
        require_request_in_scope(request.user, item, rbac.Action.MANAGE_MEMBERS)  # parity O-B1
        require_module_for_request(_makerspace(request.user, item.makerspace_id), item)
        serializer = RevokeSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        item = membership_services.revoke_request(request.user, item, serializer.validated_data.get("reason", ""))
        return Response(MembershipRequestSerializer(item, context=_admission_context(request.user, [item])).data)


class AdminMembershipRevokeM2View(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(description="Requires manage_members in this makerspace; staff role administration and waiver publishing require manage_makerspace.", tags=["Admin memberships"], request=RevokeSerializer, responses={200: AdminMembershipSerializer, **ERRORS})
    def post(self, request, pk):
        membership = get_object_or_404(rbac.scope_by_visibility_or_action(request.user, rbac.Action.MANAGE_MEMBERS, MakerspaceMembership.objects.select_related("makerspace")), pk=pk)
        require_member_in_scope(request.user, membership, rbac.Action.MANAGE_MEMBERS)  # parity O-B1
        _makerspace(request.user, membership.makerspace_id)
        serializer = RevokeSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        membership = membership_services.revoke_membership(request.user, membership, serializer.validated_data.get("reason", ""))
        membership = MakerspaceMembership.objects.select_related(
            "user", "assigned_role"
        ).get(pk=membership.pk)
        return Response(
            AdminMembershipSerializer(
                membership,
                context=_membership_context(request.user, membership),
            ).data
        )


class AdminMembershipRoleM2View(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        description="Requires manage_members; staff role changes require manage_makerspace. Replace the complete role set using exactly one of role_id or role_ids. Duplicate IDs are ignored; Space Manager and Member are exclusive. Unknown or foreign IDs return 404.",
        tags=["Admin memberships"], request=RoleSetInputSerializer,
        responses={200: AdminMembershipSerializer, **ERRORS, 400: ROLE_SET_VALIDATION_ERROR},
    )
    def patch(self, request, pk):
        # Role sets live on staff rows (any role) and community rows (Member only), so look in both.
        membership = get_object_or_404(rbac.scope_by_visibility_or_action(request.user, rbac.Action.MANAGE_MEMBERS, MakerspaceMembership.both_tracks().select_related("makerspace")), pk=pk)
        require_member_in_scope(request.user, membership, rbac.Action.MANAGE_MEMBERS)  # parity O-B1
        makerspace = _makerspace(request.user, membership.makerspace_id)
        serializer = RoleSetInputSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        roles = resolve_role_set(makerspace, serializer.validated_data)
        membership = membership_services.change_role(request.user, membership, roles)
        membership = MakerspaceMembership.track_manager(membership.track).select_related(
            "user", "assigned_role"
        ).prefetch_related(additional_roles_prefetch()).get(pk=membership.pk)
        return Response(
            AdminMembershipSerializer(
                membership,
                context=_membership_context(request.user, membership),
            ).data
        )


class AdminWaiverView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(description="Requires manage_members in this makerspace; staff role administration and waiver publishing require manage_makerspace.", tags=["Admin memberships"], responses={200: MemberWaiverResponseSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        makerspace = _makerspace(request.user, makerspace_id)
        waiver = MakerspaceWaiver.objects.filter(makerspace=makerspace, is_active=True).first()
        return Response({"has_waiver": False} if waiver is None else {
            "has_waiver": True, "version": waiver.version, "body": waiver.body,
        })

    @extend_schema(description="Requires manage_makerspace in this makerspace to publish or clear waiver text.", tags=["Admin memberships"], request=WaiverPublishSerializer, responses={200: MemberWaiverResponseSerializer, **ERRORS})
    def put(self, request, makerspace_id):
        makerspace = _makerspace(request.user, makerspace_id, rbac.Action.MANAGE_MAKERSPACE)
        serializer = WaiverPublishSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get("clear"):
            waiver_services.deactivate_waiver(request.user, makerspace)
            return Response({"has_waiver": False})
        waiver = waiver_services.publish_waiver(request.user, makerspace, serializer.validated_data["body"], serializer.validated_data["version"])
        return Response({"has_waiver": True, "version": waiver.version})
