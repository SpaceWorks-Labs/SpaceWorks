"""The monthly staff membership summary preset (X33): status, switch, personal opt-out."""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.views_membership_l4_common import staff_space
from apps.admin_api.views_roles import ERRORS
from apps.makerspaces import membership_summary

_STATUS = inline_serializer("MembershipSummaryStatus", {
    "enabled": serializers.BooleanField(), "next_run_at": serializers.DateTimeField(allow_null=True),
    "opted_out": serializers.BooleanField()})


class MembershipSummaryInput(serializers.Serializer):
    enabled = serializers.BooleanField(required=False)
    opted_out = serializers.BooleanField(required=False)


class MembershipSummaryView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin memberships"], summary="The monthly membership summary preset",
                   description="Requires manage_members and membership.monthly_summary.",
                   responses={200: _STATUS, **ERRORS})
    def get(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, "monthly_summary")
        return Response(membership_summary.status(request.user, space))

    @extend_schema(tags=["Admin memberships"], summary="Turn the summary on or off, or opt yourself out",
                   description="`enabled` is a membership setting (Space Manager only, through the "
                               "settings-authority layer); `opted_out` is each recipient's own choice. Audited.",
                   request=MembershipSummaryInput, responses={200: _STATUS, **ERRORS})
    def put(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, "monthly_summary")
        data = MembershipSummaryInput(data=request.data)
        data.is_valid(raise_exception=True)
        result = membership_summary.status(request.user, space)
        if "enabled" in data.validated_data:
            result = membership_summary.set_enabled(request.user, space, data.validated_data["enabled"])
        if "opted_out" in data.validated_data:
            result = membership_summary.set_opt_out(request.user, space, data.validated_data["opted_out"])
        return Response(result)
