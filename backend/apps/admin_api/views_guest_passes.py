"""Decision 223: the staff guest-pass desk (roster, issue, desk sale, waiver at the desk, revoke).

Authority is `manage_members` in the pass's makerspace (the resolver 404s a space the actor
cannot see and 403s one they cannot manage). Decision 217 keeps staff-adjacent authority with the
Space Manager, so there is no new action; a handover desk that needs to issue passes can be given
`manage_members` through a custom role. Every route answers 404 while `membership.guest_passes`
(or `membership.day_passes` for the sale) is off, and every write is audited by the service.
"""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.views_membership_l4_common import staff_space
from apps.admin_api.views_roles import ERRORS
from apps.makerspaces import guest_pass_day, guest_pass_issue, guest_pass_lifecycle
from apps.makerspaces.models import DayPassProduct, GuestPass
from apps.makerspaces.serializers_guest_passes import (
    DeskSaleSerializer, PurchaseResultSerializer, RevokeInputSerializer, StaffIssueSerializer, StaffPassSerializer,
)

TAG = "Admin guest passes"


class _Pager(PageNumberPagination):
    page_size = 24


def _resolve_user(data, space, key_prefix="holder"):
    users = User.objects.filter(account_kind="member", is_active=True, retired_at__isnull=True,
                                merged_into__isnull=True)
    if data.get(f"{key_prefix}_id"):
        # Final audit 0.12.0: an id names only someone already tied to THIS space (a pass or a
        # membership row here). A bare platform id would let staff step through other tenants'
        # accounts and read each name and email back from the 201. Anyone else is named by email.
        tied = users.filter(Q(guest_passes__makerspace=space) | Q(makerspace_memberships__makerspace=space))
        user = tied.filter(pk=data[f"{key_prefix}_id"]).distinct().first()
    else:
        user = users.filter(email__iexact=data[f"{key_prefix}_email"]).first()
    if user is None:
        raise NotFound("No account matches that person.")
    return user


def _row(space, pass_id):
    return get_object_or_404(
        GuestPass.objects.select_related("holder", "sponsor", "product", "makerspace"), pk=pass_id, makerspace=space)


class GuestPassListView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "member_card_resolve"  # m17: people lookups share the card-resolve budget
    pagination_class = _Pager

    @extend_schema(tags=[TAG], summary="List a space's guest passes",
                   description="Requires manage_members and membership.guest_passes. Filter by `status` "
                               "(issued, active, expired, revoked, converted) and `kind` (event, sponsored, day).",
                   parameters=[OpenApiParameter("status", str), OpenApiParameter("kind", str),
                               # Decision 242 (PE5): sponsor, holder, search and per-event filters.
                               OpenApiParameter("sponsor", int), OpenApiParameter("holder", int),
                               OpenApiParameter("q", str, description="Holder or sponsor username."),
                               OpenApiParameter("event", int, description="Passes issued for this event.")],
                   responses={200: StaffPassSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, "guest_passes")
        rows = GuestPass.objects.filter(makerspace=space).select_related("holder", "sponsor", "product")
        for field, allowed in (("status", GuestPass.Status.values), ("kind", GuestPass.Kind.values)):
            value = request.query_params.get(field)
            if value in allowed:
                rows = rows.filter(**{field: value})
        params = request.query_params
        for field, lookup in (("sponsor", "sponsor_id"), ("holder", "holder_id")):
            if str(params.get(field, "")).isdigit():
                rows = rows.filter(**{lookup: int(params[field])})
        if str(params.get("event", "")).isdigit():
            rows = rows.filter(operation_id__startswith=f"event-{int(params['event'])}-reg-")
        if term := (params.get("q") or "").strip():
            from django.db.models import Q
            rows = rows.filter(Q(holder__username__icontains=term) | Q(sponsor__username__icontains=term))
        pager = self.pagination_class()
        return pager.get_paginated_response(
            StaffPassSerializer(pager.paginate_queryset(rows, request), many=True).data)

    @extend_schema(tags=[TAG], summary="Issue a guest pass",
                   description="Free pass for an existing account, for today or a later local day. Naming a "
                               "`sponsor_id` makes it a sponsored pass (the sponsor must be an active member). "
                               "Staff are not held to the sponsor tenure, presence or guest limit. Audited.",
                   request=StaffIssueSerializer, responses={201: StaffPassSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, "guest_passes")
        data = StaffIssueSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        sponsor = User.objects.filter(pk=values["sponsor_id"]).first() if values.get("sponsor_id") else None
        row, created = guest_pass_issue.issue_staff_pass(
            request.user, space, _resolve_user(values, space), day=values.get("day"), sponsor=sponsor,
            operation_id=values.get("operation_id"))
        return Response(StaffPassSerializer(_row(space, row.pk)).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class GuestPassRevokeView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Revoke a guest pass",
                   description="Requires manage_members. A paid day pass opens a refund case; a pending charge "
                               "is cancelled. Audited.",
                   request=RevokeInputSerializer, responses={200: StaffPassSerializer, **ERRORS})
    def post(self, request, makerspace_id, pass_id):
        space = staff_space(request.user, makerspace_id, "guest_passes")
        data = RevokeInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        guest_pass_lifecycle.revoke_pass(request.user, _row(space, pass_id), data.validated_data["reason"])
        return Response(StaffPassSerializer(_row(space, pass_id)).data)


class GuestPassDeskWaiverView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Stamp the waiver at the desk",
                   description="Records that the holder accepted the active waiver in person. Requires "
                               "manage_members. The audit entry holds the version, never the waiver text.",
                   request=None, responses={200: StaffPassSerializer, **ERRORS})
    def post(self, request, makerspace_id, pass_id):
        space = staff_space(request.user, makerspace_id, "guest_passes")
        guest_pass_lifecycle.stamp_waiver(request.user, _row(space, pass_id), at_desk=True)
        return Response(StaffPassSerializer(_row(space, pass_id)).data)


class GuestPassDeskSaleView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Sell a day pass at the desk",
                   description="Requires manage_members and membership.day_passes. A priced pass records the "
                               "amount owed; settle it through the normal payment reconciliation (cash receipt). "
                               "The pass unlocks once the charge is paid or waived.",
                   request=DeskSaleSerializer, responses={201: PurchaseResultSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, "day_passes")
        data = DeskSaleSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        product = get_object_or_404(DayPassProduct, pk=values["product_id"], makerspace=space)
        row, payment = guest_pass_day.sell_day_pass(
            request.user, space, _resolve_user(values, space), product, day=values.get("day"),
            operation_id=values.get("operation_id"))
        return Response(PurchaseResultSerializer({
            "pass_id": row.pk, "status": row.status, "payment_id": payment.pk if payment else None,
            "payment_status": payment.status if payment else None, "amount": str(product.amount),
            "currency": payment.currency if payment else product.currency}).data, status=status.HTTP_201_CREATED)
