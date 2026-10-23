"""Own security audit allowlist. Never serialize metadata or arbitrary audit rows."""

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import active_user
from apps.audit.models import AuditLog


SECURITY_ACTIONS = frozenset({
    "auth.login_succeeded", "auth.login_failed", "auth.logout", "auth.password_changed",
    "auth.password_reset_confirmed", "auth.password_reset_requested", "auth.device_login_succeeded",
    "auth.device_revoked", "auth.session_revoked", "auth.sessions_revoked", "auth.refresh_rejected",
    "auth.mfa_enabled", "auth.mfa_disabled", "auth.mfa_failed", "auth.mfa_verified",
    "auth.mfa_recovery_used", "auth.mfa_recovery_regenerated", "auth.mfa_host_recovered",
    "auth.reauthenticated", "auth.reauthentication_failed", "auth.social_identity_linked",
    "auth.social_identity_unlinked", "auth.phone_verified", "auth.email_verified",
    "auth.social_login_succeeded", "auth.social_login_failed", "auth.social_identity_link_failed",
    "auth.phone_login_succeeded", "auth.phone_login_failed", "auth.device_login_failed",
    "auth.device_grant_revoked", "auth.device_logout",
    "user.password_changed", "user.password_reset_via_email", "user.password_reset",
})


def own_security_activity(actor):
    if not active_user(actor) or actor.account_kind != "member":
        raise PermissionDenied()
    # Auth actions where this account is the actor only. An administrator's action,
    # arbitrary target strings and shared/global auth failures cannot select another user.
    return AuditLog.objects.filter(actor_id=actor.pk, action__in=SECURITY_ACTIONS).only(
        "pk", "action", "created_at").order_by("-created_at", "-pk")


class SecurityActivitySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    action = serializers.CharField()
    created_at = serializers.DateTimeField()


class SecurityActivityPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = SecurityActivitySerializer(many=True)


class SecurityActivityError(serializers.Serializer):
    detail = serializers.CharField()


class MemberSecurityActivityView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Member account"], request=None,
                   responses={200: SecurityActivityPageSerializer,
                              **{code: SecurityActivityError for code in (400, 401, 403, 429)}})
    def get(self, request):
        paginator = PageNumberPagination()
        paginator.page_size = 24
        rows = paginator.paginate_queryset(own_security_activity(request.user), request, view=self)
        response = paginator.get_paginated_response(SecurityActivitySerializer(rows, many=True).data)
        response["Cache-Control"] = "private, no-store"
        return response
