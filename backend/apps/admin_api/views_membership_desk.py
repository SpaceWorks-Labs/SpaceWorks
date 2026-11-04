"""Staff routes for titles, invite links, the renewal desk and bulk decisions (X16, X11, G16, X17).

`manage_members` in the space; each route 404s when its switch is off. Bulk decisions
also need a recent re-authentication, exactly like the single approve route.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_membership_l4 import (
    BulkDecideInputSerializer, BulkDecideResultSerializer, ExtendInputSerializer, InviteLinkCreateSerializer,
    InviteLinkCreatedSerializer, InviteLinkSerializer, MembershipIdsSerializer, MembershipTitleSerializer,
    WorklistRowSerializer,
)
from apps.admin_api.serializers_membership_plans import MembershipTermSerializer
from apps.admin_api.views_membership_l4_common import scoped_row, staff_membership, staff_space
from apps.admin_api.views_roles import ERRORS
from apps.makerspaces import membership_renewal_desk as desk, membership_titles
from apps.makerspaces.models import MembershipInviteLink, MembershipTitle

TAGS = ["Admin memberships"]


class MembershipTitleListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="List member titles", responses={200: MembershipTitleSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, "titles")
        return Response(MembershipTitleSerializer(MembershipTitle.objects.filter(makerspace=space), many=True).data)

    @extend_schema(tags=TAGS, summary="Create a member title",
                   description="Display only; never a permission. Colours are brand accent presets. Audited.",
                   request=MembershipTitleSerializer, responses={201: MembershipTitleSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, "titles")
        data = MembershipTitleSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        title = membership_titles.save_title(request.user, space, data.validated_data)
        return Response(MembershipTitleSerializer(title).data, status=201)


class MembershipTitleDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Rename, recolour or reorder a member title",
                   request=MembershipTitleSerializer, responses={200: MembershipTitleSerializer, **ERRORS})
    def patch(self, request, pk):
        title = scoped_row(request.user, MembershipTitle.objects.all(), pk, "titles")
        data = MembershipTitleSerializer(title, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        title = membership_titles.save_title(request.user, title.makerspace, data.validated_data, title=title)
        return Response(MembershipTitleSerializer(title).data)

    @extend_schema(tags=TAGS, summary="Archive a member title",
                   description="Assignments stay as history; the title leaves pickers and cards.",
                   request=None, responses={200: MembershipTitleSerializer, **ERRORS})
    def delete(self, request, pk):
        title = scoped_row(request.user, MembershipTitle.objects.all(), pk, "titles")
        return Response(MembershipTitleSerializer(membership_titles.set_archived(request.user, title, True)).data)


class InviteLinkListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="List membership invite links",
                   responses={200: InviteLinkSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, "admission_tools")
        rows = MembershipInviteLink.objects.filter(makerspace=space).select_related("plan")
        return Response(InviteLinkSerializer(rows, many=True).data)

    @extend_schema(tags=TAGS, summary="Create a multi-use membership invite link",
                   description="Optional label, plan, use limit (1-10000) and expiry. The code is returned "
                               "once; only its digest is stored. Audited.",
                   request=InviteLinkCreateSerializer, responses={201: InviteLinkCreatedSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        from apps.makerspaces.membership_invite_links import create_link
        space = staff_space(request.user, makerspace_id, "admission_tools")
        data = InviteLinkCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        link, code = create_link(request.user, space, **data.validated_data)
        link.code = code
        return Response(InviteLinkCreatedSerializer(link).data, status=201)


class InviteLinkRevokeView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Revoke a membership invite link", request=None,
                   responses={200: InviteLinkSerializer, **ERRORS})
    def post(self, request, pk):
        from apps.makerspaces.membership_invite_links import revoke_link
        link = scoped_row(request.user, MembershipInviteLink.objects.all(), pk, "admission_tools")
        return Response(InviteLinkSerializer(revoke_link(request.user, link)).data)


class RenewalWorklistView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="The renewal worklist",
                   description="Active memberships whose latest term ends within `window_days` (default 30, "
                               "max 365), is in grace, or lapsed in the last 60 days with no successor.",
                   responses={200: WorklistRowSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        from apps.makerspaces.membership_number import pattern_for
        space = staff_space(request.user, makerspace_id, "renewal_desk")
        try:
            window = max(1, min(int(request.query_params.get("window_days", 30)), 365))
        except ValueError:
            window = 30
        rows = []
        for item in desk.worklist(space, window_days=window):
            membership = item["membership"]
            membership._desk = item
            rows.append(membership)
        context = {"request": request, "pattern": pattern_for(space)}
        return Response(WorklistRowSerializer(rows, many=True, context=context).data)


class RenewalRemindersView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Remind members about their renewal",
                   description="At most one manual reminder per member per local day; others are skipped. "
                               "Sent through each member's notification channels. Audited per member.",
                   request=MembershipIdsSerializer, responses={200: inline_serializer("RenewalReminderResult", {
                       "sent": serializers.ListField(child=serializers.IntegerField()),
                       "skipped": serializers.ListField(child=serializers.IntegerField())}), **ERRORS})
    def post(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, "renewal_desk")
        data = MembershipIdsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(desk.send_reminders(request.user, space, data.validated_data["membership_ids"]))


class MembershipExtendView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Extend a membership by hand",
                   description="Moves the open term's end by `days` or to `until` (a local date), with a "
                               "required reason. Written to the term history; audited as membership.extended.",
                   request=ExtendInputSerializer, responses={200: MembershipTermSerializer, **ERRORS})
    def post(self, request, pk):
        membership = staff_membership(request.user, pk, "renewal_desk")
        data = ExtendInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        term = desk.extend(request.user, membership, **data.validated_data)
        return Response(MembershipTermSerializer(term).data)


class JoinRequestBulkDecideView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Approve or reject many join requests",
                   description="Up to 100 requests, each through the single-request service in its own "
                               "transaction; one refusal never blocks the rest. Approvals use the Member role. "
                               "Needs a recent re-authentication. Audited as membership.bulk_decided.",
                   request=BulkDecideInputSerializer, responses={200: BulkDecideResultSerializer(many=True), **ERRORS})
    def post(self, request, makerspace_id):
        from apps.makerspaces.membership_admission_bulk import bulk_decide
        from apps.makerspaces.membership_helpers import _member_role
        space = staff_space(request.user, makerspace_id, "admission_tools")
        data = BulkDecideInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        results = bulk_decide(request.user, space, values["request_ids"], decision=values["decision"],
                              role=_member_role(space), reason=values["reason"])
        return Response(BulkDecideResultSerializer(results, many=True).data)
