"""Account disable / re-enable and two-step reset in the web superadmin console (#190).

Parity with the /control/ Accounts actions: the same services (``staff_account_lifecycle``,
``mfa_reset``) decide and audit. Looking an account up is by exact user name only and the
answer carries no contact detail (no email, phone or display name), so PII masking holds.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import mfa_reset
from apps.accounts import staff_account_lifecycle as lifecycle
from apps.accounts.models import User
from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.accounts.staff_identity import is_person
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.openapi_errors import errors

TAGS = ["Platform accounts"]


class PlatformAccountSerializer(serializers.ModelSerializer):
    mfa_enabled = serializers.SerializerMethodField()
    staff_role_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "account_kind", "is_active", "access_status", "mfa_enabled", "staff_role_count")
        read_only_fields = fields

    def get_mfa_enabled(self, obj) -> bool:
        row = getattr(obj, "usermfa", None)
        return bool(row and row.enabled_at and row.secret)

    def get_staff_role_count(self, obj) -> int:
        from apps.makerspaces.models import MakerspaceMembership

        return MakerspaceMembership.staff_tracks.filter(user=obj, status="active").count()


class AccountActionReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=3, max_length=300)


class TwoStepResetSerializer(serializers.Serializer):
    rule = serializers.CharField(help_text="Which reset rule applied.")


def _person(pk):
    user = get_object_or_404(User, pk=pk, is_tenant_dump_stub=False)
    if not is_person(user):
        raise PermissionDenied("Only a personal account is managed here.")
    return user


class PlatformAccountLookupView(APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Find a personal account by its exact user name",
                   parameters=[OpenApiParameter("username", str, required=True)],
                   responses={200: PlatformAccountSerializer(many=True), **errors(401, 403)})
    def get(self, request):
        username = str(request.query_params.get("username", "")).strip()
        rows = [user for user in User.objects.filter(username__iexact=username, is_tenant_dump_stub=False)[:1]
                if username and is_person(user)]
        return Response(PlatformAccountSerializer(rows, many=True).data)


class _AccountAction(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]


class PlatformAccountDisableView(_AccountAction):
    @extend_schema(tags=TAGS, summary="Disable an account: every session ends and its staff roles are revoked",
                   request=AccountActionReasonSerializer, responses={200: PlatformAccountSerializer, **errors(400, 401, 403, 404, 423)})
    def post(self, request, pk):
        body = AccountActionReasonSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        person = _person(pk)
        lifecycle.disable_account(request.user, person.pk, reason=body.validated_data["reason"])
        person.refresh_from_db()
        return Response(PlatformAccountSerializer(person).data)


class PlatformAccountEnableView(_AccountAction):
    @extend_schema(tags=TAGS, summary="Re-enable a disabled account (staff roles stay revoked)", request=None,
                   responses={200: PlatformAccountSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        person = _person(pk)
        lifecycle.enable_account(request.user, person.pk)
        person.refresh_from_db()
        return Response(PlatformAccountSerializer(person).data)


class PlatformAccountTwoStepResetView(_AccountAction):
    @extend_schema(tags=TAGS, summary="Reset an account's two-step sign-in (every factor cleared, sessions end)",
                   request=AccountActionReasonSerializer, responses={200: TwoStepResetSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        body = AccountActionReasonSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        rule = mfa_reset.reset(request.user, _person(pk), body.validated_data["reason"])
        return Response({"rule": rule})
