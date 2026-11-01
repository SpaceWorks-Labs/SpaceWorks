from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts import mfa_challenges, mfa_policy
from apps.accounts.attestation import AttestationUnavailable
from apps.accounts.auth_cookies import set_refresh_cookies
from apps.accounts.mfa_sessions import context
from apps.accounts.serializers_mfa import (
    MFAChallengeSerializer, MFAChallengeResponseSerializer, MFACompletedSerializer,
    MFAEnrollmentSerializer, MFAPasswordSerializer, MFARecoverySerializer,
    MFAStatusSerializer, MFAVerifySerializer, MFAEnrollmentStartSerializer,
)
from apps.accounts.services_mfa import change
from apps.accounts.throttles_mfa import MFAChallengeThrottle, MFAUserThrottle
from apps.openapi_errors import errors


def _validated(cls, request):
    serializer = cls(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


class MFAStatusView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "mfa_manage"

    @extend_schema(tags=["MFA"], responses={200: MFAStatusSerializer, **errors(401, 403, 429)})
    def get(self, request):
        row = mfa_policy.credential(request.user)
        return Response({"available": mfa_policy.available(), "enabled": bool(row and row.enabled_at),
                         "required": mfa_policy.required(request.user),
                         "password_available": request.user.has_usable_password()})

    @extend_schema(tags=["MFA"], request=MFAEnrollmentStartSerializer,
                   responses={200: MFAChallengeResponseSerializer, **errors(400, 401, 403, 429, 503)})
    def post(self, request):
        from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
        mfa_policy.assert_available()
        grant = getattr(request, "device_grant", None)
        if grant is not None and grant.authority == "staff":
            # A native staff grant is only ever issued behind an enrolled factor.
            raise PermissionDenied({"detail": "Staff enroll an authenticator during device sign-in.",
                                    "code": "native_staff_mfa_managed"})
        if grant is not None:
            # Starting invalidates this device's tokens; never strand it where confirm cannot re-issue.
            from apps.accounts.services_device_tokens import assert_mobile_grant_creation_enabled
            assert_mobile_grant_creation_enabled()
        data = _validated(MFAEnrollmentStartSerializer, request)
        if not request.user.has_usable_password():
            from apps.accounts.reauthentication import require_enrollment_proof
            require_enrollment_proof(request)
        elif not request.user.check_password(data["password"]):
            raise AuthenticationFailed("Password verification failed.")
        token = request.auth
        # A device enrollment re-issues tokens on this grant, never a new one.
        device = {"grant_id": str(grant.pk), "login_method": grant.login_method,
                  "purpose": mfa_challenges.SETTINGS_ENROLL} if grant else None
        response = Response(mfa_challenges.start(request.user, context=context(
            request, surface=token.get("surface"), device=device)))
        response["Cache-Control"] = "no-store"
        return response


class MFAEnrollmentView(APIView):
    # Presented claim credentials still go through the central refusal registry.
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle, MFAChallengeThrottle, MFAUserThrottle]
    throttle_scope = "mfa_verify"

    @extend_schema(tags=["MFA"], auth=[], request=MFAChallengeSerializer,
                   responses={200: MFAEnrollmentSerializer, **errors(400, 401, 403, 429, 503)})
    def post(self, request):
        result = mfa_challenges.enroll(_validated(MFAChallengeSerializer, request)["challenge"], request)
        response = Response(result)
        response["Cache-Control"] = "no-store"
        return response


class MFAVerifyView(MFAEnrollmentView):
    enrolling = False

    @extend_schema(tags=["MFA"], auth=[], request=MFAVerifySerializer,
                   description="Complete the server-owned login context. Native staff authority requires a staff account, its fixed tenant, password, authenticator MFA and approved app attestation. Consumer login methods remain member-only. Platform device grants return device_superadmin_not_supported (403). Attestation outages return attestation_unavailable (503).",
                   responses={200: MFACompletedSerializer, **errors(400, 401, 403, 429, 503)})
    def post(self, request):
        data = _validated(MFAVerifySerializer, request)
        try:
            result = mfa_challenges.finish(data["challenge"], data["code"], request, enrolling=self.enrolling)
        except AttestationUnavailable:
            return Response({"detail": "Device attestation is unavailable.", "code": "attestation_unavailable"}, status=503)
        raw = result.pop("refresh") if "device_grant" not in result else None
        response = Response(result)
        if raw:
            set_refresh_cookies(response, raw, request)
        response["Cache-Control"] = "no-store"
        return response


class MFAConfirmView(MFAVerifyView):
    enrolling = True


class MFARecoveryView(MFAStatusView):
    http_method_names = ["post", "options"]

    @extend_schema(tags=["MFA"], request=MFAPasswordSerializer,
                   responses={200: MFARecoverySerializer, **errors(400, 401, 403, 429, 503)})
    def post(self, request):
        codes = change(request.user, _validated(MFAPasswordSerializer, request)["password"])
        response = Response({"recovery_codes": codes})
        response["Cache-Control"] = "no-store"
        return response


class MFADisableView(MFAStatusView):
    http_method_names = ["post", "options"]

    @extend_schema(tags=["MFA"], request=MFAPasswordSerializer,
                   responses={200: MFAStatusSerializer, **errors(400, 401, 403, 429, 503)})
    def post(self, request):
        change(request.user, _validated(MFAPasswordSerializer, request)["password"], disable=True)
        return Response({"available": mfa_policy.available(), "enabled": False, "required": False})
