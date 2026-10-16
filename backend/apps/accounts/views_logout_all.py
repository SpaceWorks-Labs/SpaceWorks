"""Account-wide sign-out shared by browser and native clients."""

from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from apps.accounts import audit_events
from apps.accounts.auth_cookies import clear_refresh_cookies
from apps.accounts.models_devices import DeviceGrant
from apps.accounts.services_tokens import blacklist_outstanding_tokens, revoke_device_grant
from apps.accounts.web_sessions import (
    active_sessions, legacy_sessions, revoke_legacy_session, revoke_session,
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
            sessions = list(active_sessions(user))
            legacy = list(legacy_sessions(user))
            grants = list(DeviceGrant.objects.select_for_update().filter(
                user=user, status=DeviceGrant.Status.ACTIVE,
            ))
            refresh_tokens = OutstandingToken.objects.filter(
                user=user, blacklistedtoken__isnull=True,
            ).exclude(token="").count()
            for session in sessions:
                revoke_session(user, session.jti)
            for session in legacy:
                revoke_legacy_session(user, session.jti)
            for grant in grants:
                revoke_device_grant(grant)
            blacklist_outstanding_tokens(user)
            audit_events.record_auth_event(
                user, "auth.logout_all", target=user,
                meta={"web_sessions": len(sessions), "legacy_sessions": len(legacy),
                      "devices": len(grants), "refresh_tokens": refresh_tokens},
            )
        response = Response({"web_sessions": len(sessions) + len(legacy), "devices": len(grants)})
        clear_refresh_cookies(response)
        return response
