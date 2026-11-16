"""``POST makerspaces/<id>/staff-roles/<membership>/mfa-reset``: the MFA-reset rule over HTTP.

The staff console (U-B) and Lane D's superadmin surface call it for one staff-track row
of the space. Recent re-authentication is required, and the route is in
``mfa_grace.STRICT_ROUTES``: a caller still in their own staff-MFA grace cannot reset
anyone (#135 Q-A3).
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import mfa_reset
from apps.accounts.reauthentication import require_recent_reauth
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.models import Makerspace, MakerspaceMembership


class StaffMfaResetRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=3, max_length=300,
                                   help_text="Why the person's factors are being cleared (audited).")


class StaffMfaResetView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Staff roles"], summary="Reset a staff member's two-step sign-in",
        description=(
            "Clears the person's authenticator, every passkey and their recovery codes, and ends every "
            "session. Allowed for a platform superadmin, or for this space's Space Manager only when all "
            "of the person's elevated authority is in this space and they are not a Space Manager "
            "(mfa_reset_not_allowed otherwise). Needs recent re-authentication."),
        request=StaffMfaResetRequestSerializer,
        responses={200: inline_serializer("StaffMfaResetResult", {
            "reset": serializers.BooleanField(), "rule": serializers.ChoiceField(choices=("superadmin", "space_manager")),
        }), **{code: ErrorSerializer for code in (400, 401, 403, 404)}},
    )
    def post(self, request, makerspace_id, membership_id):
        space = get_object_or_404(Makerspace, pk=makerspace_id)
        row = get_object_or_404(MakerspaceMembership.staff_tracks.select_related("user"),
                                pk=membership_id, makerspace=space)
        serializer = StaffMfaResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if mfa_reset.rule_for(request.user, row.user, space) is None:
            raise mfa_reset.MfaResetNotAllowed()
        require_recent_reauth(request)
        rule = mfa_reset.reset(request.user, row.user, serializer.validated_data["reason"], space)
        response = Response({"reset": True, "rule": rule})
        response["Cache-Control"] = "private, no-store"
        return response
