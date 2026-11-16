"""Staff-role invitations: list, resend and revoke (staff), and accept (the invitee).

Invitations are created by ``POST admin/makerspaces/<id>/staff-roles/`` with an email.
No response here carries the accept link; it goes to the invitee only.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts import rbac, services_staff_invitations as service
from apps.accounts.permissions import HasMakerspaceAction
from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.accounts.serializers_staff_invitations import (
    StaffInvitationAcceptSerializer, StaffInvitationAcceptedSerializer, StaffInvitationDeliverySerializer,
    StaffInvitationSerializer,
)
from apps.accounts.staff_invitation_acceptance import accept
from apps.accounts.staff_invitation_delivery import deliver
from apps.openapi_errors import errors

GATE_WRITE_ERRORS = {
    423: OpenApiResponse(description="Makerspace writes are frozen for tenant migration (`tenant_gated`)."),
    **errors(503),
}


class StaffInvitationListView(RecentReauthenticationMixin, GenericAPIView):
    permission_classes = [IsAuthenticated, HasMakerspaceAction]
    required_action = rbac.Action.MANAGE_MAKERSPACE
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "staff_invite"
    serializer_class = StaffInvitationSerializer

    def get_queryset(self):
        return service.scoped(self.request.user).filter(
            makerspace_id=self.kwargs["makerspace_id"]).select_related("role").order_by("-created_at", "-id")

    @extend_schema(tags=["Staff invitations"], summary="List a makerspace's staff-role invitations",
                   description="Newest first. The invitee address is masked for a superadmin without a PII "
                               "window. Never includes the accept link.",
                   responses={200: StaffInvitationSerializer(many=True), **errors(400, 401, 403, 404, 429)})
    def get(self, request, makerspace_id):
        from apps.makerspaces.models import Makerspace
        from apps.makerspaces.platform import feature_enabled
        space = get_object_or_404(rbac.scope_by_action(request.user, self.required_action,
                                                      Makerspace.objects.all(), "id"), pk=makerspace_id)
        if not feature_enabled(space, "staff.invitations"):
            from apps.makerspaces.guards import feature_off
            raise feature_off("staff.invitations", "Staff invitations are turned off for this makerspace.")
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(self.get_serializer(page, many=True).data)


class StaffInvitationRevokeView(StaffInvitationListView):
    http_method_names = ["post", "options"]

    @extend_schema(tags=["Staff invitations"], summary="Revoke an open staff-role invitation", request=None,
                   responses={200: StaffInvitationSerializer, **errors(400, 401, 403, 404, 429), **GATE_WRITE_ERRORS})
    def post(self, request, makerspace_id, invitation_id):
        row = service.revoke(request.user, makerspace_id, invitation_id)
        return Response(self.get_serializer(row).data)


class StaffInvitationResendView(StaffInvitationRevokeView):
    @extend_schema(tags=["Staff invitations"], summary="Send a fresh link for an open invitation",
                   description="The old link stops working. The response says whether the email was sent; "
                               "the link itself goes to the invitee only.",
                   request=None,
                   responses={200: StaffInvitationDeliverySerializer, **errors(400, 401, 403, 404, 429),
                              **GATE_WRITE_ERRORS})
    def post(self, request, makerspace_id, invitation_id):
        row, raw = service.resend(request.user, makerspace_id, invitation_id)
        response = Response({**self.get_serializer(row).data, **deliver(row, raw)})
        response["Cache-Control"] = "no-store"
        return response


class StaffInvitationAcceptView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    login_ip_guard = True  # S-C: platform IP rules, automatic blocks, Turnstile
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "staff_invite_accept"
    serializer_class = StaffInvitationAcceptSerializer

    @extend_schema(
        tags=["Staff invitations"], summary="Accept a staff-role invitation (two steps)",
        description=(
            "Signed in to your own account. First call without `code`: your account email must equal the "
            "invitation address (`invite_email_mismatch`, 403); a 6-digit code is emailed to it and the answer "
            "is `challenge_required: true`. Second call with `code`: the staff role is granted in that "
            "makerspace (`proof_failed`, 400, for a wrong code; `already_staff`, 409). Never creates an account "
            "and never marks the email verified. Both steps require staff invitations and the email module "
            "(`feature_disabled` or `module_disabled`, 404)."),
        request=StaffInvitationAcceptSerializer,
        responses={200: StaffInvitationAcceptedSerializer, **errors(400, 401, 403, 404, 409, 429), **GATE_WRITE_ERRORS},
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response = Response(accept(request, **serializer.validated_data))
        response["Cache-Control"] = "no-store"
        return response
