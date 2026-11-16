from django.db.models import Prefetch, Q
from django.utils import timezone
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.staff_identity import person_q
from apps.accounts import rbac
from apps.accounts.models import User
from apps.hardware_requests import direct_loan_workflow
from apps.hardware_requests.direct_loan_serializers import (
    DirectLoanIssueSerializer,
    DirectLoanMemberSerializer,
    DirectLoanReturnSerializer,
    DirectLoanSerializer,
)
from apps.hardware_requests.models import HardwareRequestItem, PublicToolLoan
from apps.hardware_requests.permissions import CanIssueDirectLoan, CanReturnDirectLoan
from apps.hardware_requests.view_helpers import ACTION_ERROR_RESPONSES, ERROR_503
from apps.makerspaces.guards import require_feature
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.origin_scope import origin_scoped_makerspace_id
from apps.makerspaces.platform import module_enabled


class DirectLoanListCreateView(generics.ListAPIView):
    permission_classes = [CanIssueDirectLoan]
    serializer_class = DirectLoanSerializer

    def get_queryset(self):
        makerspace_id = self.kwargs["makerspace_id"]
        require_feature(makerspace_id, "inventory.self_checkout")
        _require(self.request.user, rbac.Action.ISSUE_DIRECT_LOAN, makerspace_id)
        queryset = PublicToolLoan.objects.select_related(
            "container", "request", "request__issued_by", "requester"
        ).prefetch_related(
            Prefetch(
                "request__items",
                queryset=HardwareRequestItem.objects.select_related("product").order_by("product__name"),
            )
        ).filter(makerspace_id=makerspace_id, source=PublicToolLoan.Source.ADMIN_DIRECT)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if self.request.query_params.get("overdue") == "true":  # decision 242: IN4
            queryset = queryset.filter(returned_at__isnull=True, due_at__lt=timezone.now())
        if term := (self.request.query_params.get("search") or "").strip():
            queryset = queryset.filter(
                Q(requester__username__icontains=term) | Q(requester__first_name__icontains=term)
                | Q(requester__last_name__icontains=term) | Q(requester__email__icontains=term)
            )
        return queryset.order_by("-checked_out_at")

    @extend_schema(
        tags=["Admin requests"],
        summary="List direct handout loans",
        parameters=[OpenApiParameter("status", str, required=False), OpenApiParameter("overdue", bool, required=False),
                    OpenApiParameter("search", str, required=False,
                                     description="Borrower name, username or email (decision 242).")],
        responses={200: DirectLoanSerializer(many=True), **ACTION_ERROR_RESPONSES},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["Admin requests"],
        summary="Issue direct handout without public request",
        request=DirectLoanIssueSerializer,
        responses={201: DirectLoanSerializer, **ACTION_ERROR_RESPONSES, 503: ERROR_503},
    )
    def post(self, request, makerspace_id, *args, **kwargs):
        makerspace = _makerspace_for_action(request.user, rbac.Action.ISSUE_DIRECT_LOAN, makerspace_id)
        require_feature(makerspace, "inventory.self_checkout")
        _require(request.user, rbac.Action.ISSUE_DIRECT_LOAN, makerspace.id)
        serializer = DirectLoanIssueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        container_id = serializer.validated_data.get("container_id")
        if container_id is not None and not module_enabled(makerspace, "containers"):
            container_id = None
        loan = direct_loan_workflow.issue_direct_loan(
            makerspace,
            request.user,
            borrower=_borrower_for_makerspace(makerspace, serializer.validated_data["borrower_id"]),
            evidence_id=serializer.validated_data["evidence_id"],
            remark=serializer.validated_data.get("remark", ""),
            qr_payloads=serializer.validated_data.get("qr_payloads") or [],
            items=serializer.validated_data.get("items") or [],
            container_id=container_id,
            kit_checklist=serializer.validated_data["kit_checklist"],
        )
        return Response(DirectLoanSerializer(loan).data, status=status.HTTP_201_CREATED)


class DirectLoanReturnView(APIView):
    permission_classes = [CanReturnDirectLoan]

    @extend_schema(
        tags=["Admin requests"],
        summary="Return direct handout loan",
        request=DirectLoanReturnSerializer,
        responses={200: DirectLoanSerializer, **ACTION_ERROR_RESPONSES, 503: ERROR_503},
    )
    def post(self, request, pk, *args, **kwargs):
        # Only admin_direct loans use this path; a public self-checkout loan must
        # go through the QR/requester return flow, not the admin direct-return.
        allowed = rbac.makerspaces_for_action(request.user, rbac.Action.RETURN_REQUEST)
        origin_scope = origin_scoped_makerspace_id(request)
        if origin_scope is not None:
            allowed = (
                {origin_scope}
                if allowed is rbac.ALL
                else set(allowed) & {origin_scope}
            )
        queryset = PublicToolLoan.objects.filter(
            source=PublicToolLoan.Source.ADMIN_DIRECT
        )
        if allowed is not rbac.ALL:
            queryset = queryset.filter(makerspace_id__in=allowed)
        loan = get_object_or_404(queryset, pk=pk)
        require_feature(loan.makerspace, "inventory.self_checkout")
        _require(request.user, rbac.Action.RETURN_REQUEST, loan.makerspace_id)
        serializer = DirectLoanReturnSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        returned = direct_loan_workflow.return_direct_loan(
            loan,
            request.user,
            serializer.validated_data["evidence_id"],
            serializer.validated_data["notes"],
            serializer.validated_data["resolutions"],
            qr_payload=serializer.validated_data.get("qr_payload", ""),
            kit_checklist=serializer.validated_data["kit_checklist"],
        )
        return Response(DirectLoanSerializer(returned).data)


class DirectLoanMemberListView(generics.ListAPIView):
    permission_classes = [CanIssueDirectLoan]
    serializer_class = DirectLoanMemberSerializer

    @extend_schema(
        tags=["Admin requests"],
        summary="List eligible direct-loan members",
        responses={200: DirectLoanMemberSerializer(many=True), **ACTION_ERROR_RESPONSES},
    )
    def get_queryset(self):
        makerspace_id = self.kwargs["makerspace_id"]
        makerspace = _makerspace_for_action(self.request.user, rbac.Action.ISSUE_DIRECT_LOAN, makerspace_id)
        require_feature(makerspace, "inventory.self_checkout")
        _require(self.request.user, rbac.Action.ISSUE_DIRECT_LOAN, makerspace.id)
        members = list(MakerspaceMembership.objects.select_related("user").filter(
            person_q("user__"),
            makerspace=makerspace,
            status="active",
            user__is_active=True,
            user__access_status=User.AccessStatus.ACTIVE,
        ).order_by("user__display_name", "user__username"))
        # Live guest-pass holders are valid borrowers too (decision 223); see `_borrower_for_makerspace`.
        from apps.hardware_requests.direct_loan_guests import guest_pass_rows
        return members + guest_pass_rows(makerspace, exclude_user_ids=[row.user_id for row in members])


def _borrower_for_makerspace(makerspace, borrower_id):
    membership = MakerspaceMembership.objects.select_related("user").filter(
        person_q("user__"),
        makerspace=makerspace,
        user_id=borrower_id,
        status="active",
        user__is_active=True,
        user__access_status=User.AccessStatus.ACTIVE,
    ).first()
    if membership is None:
        # Decision 223: a person holding a live guest pass here may be handed items too (the
        # workflow then enforces the pass's borrowing mode, waiver and presence).
        from apps.makerspaces.guest_pass_queries import active_pass_for
        guest = User.objects.filter(person_q(), pk=borrower_id).first()
        if guest is None or active_pass_for(guest, makerspace) is None:
            raise PermissionDenied()
        return guest
    return membership.user


def _makerspace_for_action(user, action, makerspace_id):
    scoped = rbac.scope_by_action(user, action, Makerspace.objects.all(), field="id")
    return get_object_or_404(scoped, pk=makerspace_id)


def _require(user, action, makerspace_id):
    # rbac.can() only checks membership/action, not account standing. Mirror the
    # active-status gate the IsStaff/HasMakerspaceAction permissions enforce so a
    # suspended user with an unexpired JWT can't keep issuing/returning loans.
    if getattr(user, "access_status", None) != User.AccessStatus.ACTIVE:
        raise PermissionDenied()
    if getattr(user, "must_change_password", False):
        raise PermissionDenied()
    if not rbac.can(user, action, makerspace_id):
        raise PermissionDenied()
