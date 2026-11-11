"""Parity O-B2 staff routes: bulk actions on the member register, and "ask the applicant for changes".

Both need `manage_members` in the space (bulk card actions also `manage_member_cards`), a recent re-authentication,
and their own `membership.*` switch (404 when off). The services do the per-row work; see
`makerspaces/member_register_bulk.py` and `makerspaces/membership_admission_changes.py`.
"""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_member_memberships import MembershipRequestSerializer
from apps.admin_api.serializers_membership_l4 import BulkDecideResultSerializer
from apps.admin_api.views_member_memberships import _admission_context
from apps.admin_api.views_membership_l4_common import staff_space
from apps.admin_api.views_roles import ERRORS
from apps.makerspaces import member_register_bulk as bulk
from apps.makerspaces import membership_admission_changes as changes
from apps.makerspaces.models import MembershipRequest

TAGS = ["Admin memberships"]


class RegisterBulkInputSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=tuple(bulk.ACTIONS))
    membership_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1, max_length=bulk.MAX_ROWS,
                                           required=False)
    filter = serializers.DictField(required=False)
    title_id = serializers.IntegerField(required=False)
    primary = serializers.BooleanField(required=False, default=False)
    unit_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        if ("membership_ids" in attrs) == ("filter" in attrs):
            raise serializers.ValidationError("Send either membership_ids or filter.")
        return attrs


class RequestChangesInputSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000)


class MemberRegisterBulkView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Apply one action to many members from the register",
                   description="Up to 200 members (explicit ids, or a filter in the shared member-filter contract "
                               "that matches at most 200). Each member runs the existing single-member service in "
                               "its own transaction; the result lists every member with ok/code, so one refusal never "
                               "blocks the rest. Actions: assign_title (title_id, primary), move_unit (unit_id or "
                               "null), send_reminder, issue_cards, email_cards. Members outside the caller's unit "
                               "scope are reported not_found. Needs a recent re-authentication. Audited as "
                               "membership.register_bulk_applied (counts) next to each service's own entries.",
                   request=RegisterBulkInputSerializer, responses={200: BulkDecideResultSerializer(many=True), **ERRORS})
    def post(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, "register_bulk")
        data = RegisterBulkInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        options = {key: values[key] for key in ("title_id", "primary", "unit_id") if key in values}
        results = bulk.apply_bulk(request.user, space, values["action"], membership_ids=values.get("membership_ids"),
                                  filter_params=values.get("filter"), options=options)
        return Response(BulkDecideResultSerializer(results, many=True).data)


class JoinRequestChangesView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Send a join request back to the applicant for changes",
                   description="Allowed once per request, from requested or awaiting_vouches, behind "
                               "membership.ask_changes. The applicant is notified with the reason, edits their "
                               "answers and resubmits once. Audited as membership.changes_requested.",
                   request=RequestChangesInputSerializer, responses={200: MembershipRequestSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        space = staff_space(request.user, makerspace_id, "ask_changes")
        row = get_object_or_404(rbac.scope_by_action(request.user, rbac.Action.MANAGE_MEMBERS,
                                                     MembershipRequest.objects.filter(makerspace=space)), pk=pk)
        data = RequestChangesInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        row = changes.request_changes(request.user, row, data.validated_data["reason"])
        return Response(MembershipRequestSerializer(row, context=_admission_context(request.user, [row])).data)
