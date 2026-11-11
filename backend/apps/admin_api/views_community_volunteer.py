"""Decision 223 (k): staff routes for volunteer hours and the membership credit they earn (lane L3b).

`manage_members` logs hours for a member (approved at once), decides pending entries, imports verified event
shifts and voids an unused credit. Every route answers 404 while `membership.volunteer_credit` is off, and
every write is audited by the service. Credits reduce a membership charge only through the charge path
(`volunteer_credit.reduce_charge`); nothing here edits a price.
"""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.views_membership_l4_common import staff_space
from apps.admin_api.views_roles import ERRORS
from apps.makerspaces import volunteer_credit, volunteer_hours
from apps.makerspaces.models import VolunteerCredit, VolunteerHourEntry
from apps.makerspaces.serializers_community import (
    VoidInputSerializer, VolunteerCreditSerializer, VolunteerDecisionSerializer, VolunteerEntrySerializer,
    VolunteerImportResultSerializer, VolunteerLogInputSerializer,
)

TAG = "Admin community"
FEATURE = "volunteer_credit"


class _Pager(PageNumberPagination):
    page_size = 24


class VolunteerHoursListView(APIView):
    permission_classes = [IsActiveStaff]
    pagination_class = _Pager

    @extend_schema(tags=[TAG], summary="List volunteer hour entries",
                   description="Requires manage_members and membership.volunteer_credit. Filter by `status` "
                               "(pending, approved, rejected) or `member_id`.",
                   parameters=[OpenApiParameter("status", str), OpenApiParameter("member_id", int)],
                   responses={200: VolunteerEntrySerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, FEATURE)
        rows = VolunteerHourEntry.objects.filter(makerspace=space).select_related("member")
        if request.query_params.get("status") in VolunteerHourEntry.Status.values:
            rows = rows.filter(status=request.query_params["status"])
        if request.query_params.get("member_id", "").isdigit():
            rows = rows.filter(member_id=int(request.query_params["member_id"]))
        pager = _Pager()
        return pager.get_paginated_response(
            VolunteerEntrySerializer(pager.paginate_queryset(rows, request), many=True).data)

    @extend_schema(tags=[TAG], summary="Log volunteer hours for a member",
                   description="Staff-logged hours are approved at once and may convert into a credit. The "
                               "member must hold an active membership. Audited.",
                   request=VolunteerLogInputSerializer, responses={201: VolunteerEntrySerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, FEATURE)
        data = VolunteerLogInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        member = User.objects.filter(pk=values.pop("member_id", None)).first()
        if member is None:
            raise NotFound("No account matches that member.")
        entry = volunteer_hours.log_hours(request.user, space, member, by_staff=True, **values)
        return Response(VolunteerEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class VolunteerHoursDecideView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Approve or reject a pending volunteer entry",
                   description="Approving converts approved minutes into credits when the policy asks for it. "
                               "409 `entry_not_pending` once decided. Audited.",
                   request=VolunteerDecisionSerializer, responses={200: VolunteerEntrySerializer, **ERRORS})
    def post(self, request, makerspace_id, entry_id):
        space = staff_space(request.user, makerspace_id, FEATURE)
        entry = get_object_or_404(VolunteerHourEntry.objects.select_related("member"), pk=entry_id, makerspace=space)
        data = VolunteerDecisionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        row = volunteer_hours.review_entry(request.user, entry, approve=data.validated_data["approve"],
                                           note=data.validated_data.get("note", ""))
        return Response(VolunteerEntrySerializer(row).data)


class VolunteerHoursImportView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Offer verified event-shift hours for approval",
                   description="Creates pending entries from verified event contribution hours not yet "
                               "imported; needs events.volunteering. Importing twice creates nothing new.",
                   request=None, responses={200: VolunteerImportResultSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, FEATURE)
        from apps.events.volunteer_hours_adapter import import_verified_hours
        return Response({"created": import_verified_hours(request.user, space)})


class VolunteerCreditListView(APIView):
    permission_classes = [IsActiveStaff]
    pagination_class = _Pager

    @extend_schema(tags=[TAG], summary="List volunteer credits",
                   description="Requires manage_members and membership.volunteer_credit. Filter by `member_id`.",
                   parameters=[OpenApiParameter("member_id", int)],
                   responses={200: VolunteerCreditSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, FEATURE)
        rows = VolunteerCredit.objects.filter(makerspace=space).select_related("member").order_by("-created_at", "-pk")
        if request.query_params.get("member_id", "").isdigit():
            rows = rows.filter(member_id=int(request.query_params["member_id"]))
        pager = _Pager()
        return pager.get_paginated_response(
            VolunteerCreditSerializer(pager.paginate_queryset(rows, request), many=True).data)


class VolunteerCreditVoidView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Void an unused volunteer credit",
                   description="Only an available credit can be voided; an applied one is history. Audited.",
                   request=VoidInputSerializer, responses={200: VolunteerCreditSerializer, **ERRORS})
    def post(self, request, makerspace_id, credit_id):
        space = staff_space(request.user, makerspace_id, FEATURE)
        credit = get_object_or_404(VolunteerCredit, pk=credit_id, makerspace=space)
        data = VoidInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(VolunteerCreditSerializer(
            volunteer_credit.void_credit(request.user, credit, data.validated_data.get("reason", ""))).data)
