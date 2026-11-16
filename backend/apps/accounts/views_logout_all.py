"""Account-wide sign-out shared by browser and native clients."""

from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from apps.accounts import audit_events
from apps.accounts.models import User
from apps.accounts.auth_cookies import clear_refresh_cookies
from apps.accounts.models_devices import DeviceGrant
from apps.accounts.web_sessions import (
    active_sessions, legacy_sessions,
)
from apps.hardware_requests.exceptions import ErrorSerializer


class LogoutAllResponseSerializer(serializers.Serializer):
    web_sessions = serializers.IntegerField(
        min_value=0, help_text="Revoked browser sessions, including legacy sessions.",
    )
    devices = serializers.IntegerField(min_value=0)


class LogoutAllView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Auth"], summary="Sign out of every browser and device session",
        request=None,
        responses={
            200: LogoutAllResponseSerializer,
            401: OpenApiResponse(ErrorSerializer),
            403: OpenApiResponse(ErrorSerializer),
        },
    )
    def post(self, request):
        user = request.user
        with transaction.atomic():
            user = User.objects.select_for_update(no_key=True).get(pk=user.pk)
            sessions = list(active_sessions(user))
            legacy = list(legacy_sessions(user))
            grants = list(DeviceGrant.objects.filter(
                user=user, status=DeviceGrant.Status.ACTIVE,
            ))
            refresh_tokens = OutstandingToken.objects.filter(
                user=user, blacklistedtoken__isnull=True,
            ).exclude(token="").count()
            from apps.accounts.credential_revocation import revoke_account_sessions
            revoke_account_sessions(user)
            audit_events.record_auth_event(
                user, "auth.logout_all", target=user,
                meta={"web_sessions": len(sessions), "legacy_sessions": len(legacy),
                      "devices": len(grants), "refresh_tokens": refresh_tokens},
            )
        response = Response({"web_sessions": len(sessions) + len(legacy), "devices": len(grants)})
        from apps.accounts.session_context import token_context
        from apps.accounts.surface_policy import token_kind
        context = token_context(request.auth) if request.auth else token_kind(user)
        clear_refresh_cookies(response, context=context, request=request)
        return response
