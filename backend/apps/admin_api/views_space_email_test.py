"""POST makerspace/<id>/email/test: the test a space's own SMTP account must pass before it is used (A19).

`MANAGE_MAKERSPACE`, like every other write to the space's transport settings. The message goes to the signed-in
staff member's own address only, so the endpoint cannot be used to relay mail to a third party.
"""

from django.shortcuts import get_object_or_404
from django.utils.translation import gettext
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff, require_action
from apps.integrations.mail_providers.probe_space import probe_space_smtp
from apps.makerspaces.servability import servable_queryset
from apps.openapi_errors import errors


class SpaceEmailTestResultSerializer(serializers.Serializer):
    accepted = serializers.BooleanField()
    code = serializers.ChoiceField(choices=(
        "provider_accepted", "smtp_not_configured", "smtp_probe_failed", "smtp_probe_not_accepted", "no_account_email"))
    smtp_verified = serializers.BooleanField()
    smtp_verified_at = serializers.DateTimeField(allow_null=True)


class MakerspaceEmailTestView(APIView):
    permission_classes = [IsActiveStaff]
    http_method_names = ["post", "options"]

    @extend_schema(
        tags=["Makerspaces"], summary="Send a test message through the space's own SMTP account", request=None,
        responses={200: SpaceEmailTestResultSerializer, 422: SpaceEmailTestResultSerializer, **errors(401, 403, 404)},
    )
    def post(self, request, makerspace_id):
        require_action(request.user, rbac.Action.MANAGE_MAKERSPACE, makerspace_id)
        space = get_object_or_404(servable_queryset(), pk=makerspace_id)
        recipient = (request.user.email or "").strip()
        if not recipient:
            return self._reply(space, "no_account_email", False, None)
        result = probe_space_smtp(actor=request.user, makerspace=space, recipient=recipient)
        space.refresh_from_db(fields=["smtp_verified_fingerprint", "smtp_verified_at"])
        return self._reply(space, result.code, result.accepted, space.smtp_verified_at)

    @staticmethod
    def _reply(space, code, accepted, verified_at):
        from apps.integrations.space_smtp_gate import smtp_verified
        body = {"accepted": accepted, "code": code, "smtp_verified": smtp_verified(space),
                "smtp_verified_at": verified_at or space.smtp_verified_at}
        return Response(body, status=status.HTTP_200_OK if accepted else status.HTTP_422_UNPROCESSABLE_ENTITY)
