"""Public proof-confirmation endpoints; old sessions never become valid again."""

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.authentication import SpaceWorksJWTAuthentication
from apps.accounts.serializers_account_restore import (
    AccountRestoreEmailSerializer, AccountRestorePhoneSerializer, AccountRestoreResultSerializer,
    AccountRestoreSocialStartSerializer, AccountRestoreSocialCompleteSerializer, AccountRestoreSocialResultSerializer,
)
from apps.accounts.throttles import (
    PasswordResetConfirmEmailThrottle,
    PhoneLoginConfirmThrottle, PhoneConfirmNumberThrottle, DeviceLoginThrottle, DeviceLoginUserThrottle,
)
from apps.openapi_errors import errors


def _response(data):
    response = Response(data)
    response["Cache-Control"] = "private, no-store"
    return response


def _restored():
    return _response({"restored": True, "detail": "Your account is restored. Sign in again. Memberships remain revoked."})


class RestoreView(APIView):
    authentication_classes = [SpaceWorksJWTAuthentication]
    permission_classes = [AllowAny]
    login_ip_guard = True  # S-C: platform IP rules, automatic blocks, Turnstile


class AccountRestoreEmailView(RestoreView):
    throttle_classes = [ScopedRateThrottle, PasswordResetConfirmEmailThrottle]
    throttle_scope = "password_reset_confirm"

    @extend_schema(tags=["Accounts"], auth=[], request=AccountRestoreEmailSerializer,
                   responses={200: AccountRestoreResultSerializer, **errors(400, 401, 403, 429)},
                   description="Consume a single-use, attempt-capped, 24-hour restore link delivered by password recovery. "
                               "Requires a new password; refuses at the purge deadline or once any purge started.")
    def post(self, request):
        from apps.accounts.account_restore_email import confirm_email
        data = AccountRestoreEmailSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        confirm_email(**data.validated_data)
        return _restored()


class AccountRestorePhoneView(RestoreView):
    throttle_classes = [PhoneLoginConfirmThrottle, PhoneConfirmNumberThrottle]

    @extend_schema(tags=["Accounts"], auth=[], request=AccountRestorePhoneSerializer,
                   responses={200: AccountRestoreResultSerializer, **errors(400, 401, 403, 409, 429, 503)},
                   description="Consume a restore OTP from phone/login/start for an archived phone-only account. "
                               "Device delivery must prove the exact attestation challenge. Requires a new password.")
    def post(self, request):
        from apps.accounts.account_restore_phone import confirm_phone
        data = AccountRestorePhoneSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        confirm_phone(data.validated_data)
        return _restored()


class AccountRestoreSocialStartView(RestoreView):
    throttle_classes = [DeviceLoginThrottle, DeviceLoginUserThrottle]

    @extend_schema(tags=["Accounts"], auth=[], request=AccountRestoreSocialStartSerializer,
                   responses={200: AccountRestoreSocialResultSerializer, **errors(400, 401, 403, 429, 503)},
                   description="Start a five-minute, single-use fresh sign-in for an already-linked provider. "
                               "Browser delivery requires a registered member origin and same-origin redirect. Native Apple/Google delivery binds an approved app attestation challenge and audience. "
                               "Only accounts without email or phone can restore through this flow. Never links identities.")
    def post(self, request):
        from apps.accounts.account_restore_social import start_social
        data = AccountRestoreSocialStartSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return _response(start_social(request, **data.validated_data))


class AccountRestoreSocialCompleteView(RestoreView):
    throttle_classes = [DeviceLoginThrottle]

    @extend_schema(tags=["Accounts"], auth=[], request=AccountRestoreSocialCompleteSerializer,
                   responses={200: AccountRestoreResultSerializer, **errors(400, 401, 403, 429, 503)},
                   description="Fresh auth_time within five minutes is mandatory for Apple, Google and OIDC. "
                               "OIDC authorization requests prompt=login and max_age=0. Providers without that proof "
                               "cannot restore. Account eligibility and the original linked subject are rechecked under lock.")
    def post(self, request):
        from apps.accounts.account_restore_social import complete_social
        data = AccountRestoreSocialCompleteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        complete_social(request, **data.validated_data)
        return _restored()
