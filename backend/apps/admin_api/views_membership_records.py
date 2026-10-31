"""Staff routes for one member's record, titles, consent ledger and history (X13, X16, X10, X28).

`manage_members` in the membership's space; each route 404s when its switch is off.
"""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_membership_l4 import (
    MembershipRecordInputSerializer, MembershipRecordSerializer, TitleAssignInputSerializer,
    TitleAssignmentSerializer,
)
from apps.admin_api.views_membership_l4_common import staff_membership
from apps.admin_api.views_roles import ERRORS
from apps.makerspaces import membership_titles
from apps.makerspaces.membership_history_timeline import timeline
from apps.makerspaces.membership_records import record_for, update_record
from apps.makerspaces.models import MembershipTitle, MembershipTitleAssignment
from apps.makerspaces.serializers_membership_l4 import ConsentRowSerializer, TimelineEntrySerializer

TAGS = ["Admin memberships"]


class MembershipRecordView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Read a member's record fields",
                   description="Requires manage_members and membership.records. Staff notes are staff-only.",
                   responses={200: MembershipRecordSerializer, **ERRORS})
    def get(self, request, pk):
        membership = staff_membership(request.user, pk, "records")
        return Response(MembershipRecordSerializer(record_for(membership), context={"request": request}).data)

    @extend_schema(tags=TAGS, summary="Change a member's record fields",
                   description="State code (2 digits), GSTIN (validated; its first two digits must match the "
                               "state code) and staff notes. Audited by field name only.",
                   request=MembershipRecordInputSerializer, responses={200: MembershipRecordSerializer, **ERRORS})
    def put(self, request, pk):
        membership = staff_membership(request.user, pk, "records")
        data = MembershipRecordInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        row = update_record(request.user, membership, data.validated_data)
        return Response(MembershipRecordSerializer(row, context={"request": request}).data)


class MembershipTitleAssignmentsView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="A member's display titles",
                   responses={200: TitleAssignmentSerializer(many=True), **ERRORS})
    def get(self, request, pk):
        membership = staff_membership(request.user, pk, "titles")
        rows = MembershipTitleAssignment.objects.filter(membership=membership).select_related("title")
        return Response(TitleAssignmentSerializer(rows, many=True).data)

    @extend_schema(tags=TAGS, summary="Give a member a display title",
                   description="Titles grant no permissions. `primary` makes it the one printed on the card. "
                               "Audited as membership.title_assigned.",
                   request=TitleAssignInputSerializer, responses={200: TitleAssignmentSerializer(many=True), **ERRORS})
    def post(self, request, pk):
        membership = staff_membership(request.user, pk, "titles")
        data = TitleAssignInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        title = get_object_or_404(MembershipTitle, pk=data.validated_data["title_id"],
                                  makerspace_id=membership.makerspace_id)
        membership_titles.assign(request.user, membership, title, primary=data.validated_data["primary"])
        return self.get(request, pk)


class MembershipTitleUnassignView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Remove a display title from a member",
                   request=None, responses={200: TitleAssignmentSerializer(many=True), **ERRORS})
    def delete(self, request, pk, title_id):
        membership = staff_membership(request.user, pk, "titles")
        title = get_object_or_404(MembershipTitle, pk=title_id, makerspace_id=membership.makerspace_id)
        membership_titles.unassign(request.user, membership, title)
        return MembershipTitleAssignmentsView().get(request, pk)


class MembershipConsentLedgerView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="A member's consent ledger (read-only)",
                   description="What the member agreed to and withdrew. Only the member changes it.",
                   responses={200: ConsentRowSerializer(many=True), **ERRORS})
    def get(self, request, pk):
        from apps.makerspaces.membership_consent import ledger
        return Response(ConsentRowSerializer(ledger(staff_membership(request.user, pk, "consent")), many=True).data)


class MembershipStaffHistoryView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="A membership's history in words",
                   description="The staff view includes the reasons staff wrote (an extension's why).",
                   responses={200: TimelineEntrySerializer(many=True), **ERRORS})
    def get(self, request, pk):
        membership = staff_membership(request.user, pk, "history")
        return Response(TimelineEntrySerializer(timeline(membership, for_staff=True), many=True).data)
