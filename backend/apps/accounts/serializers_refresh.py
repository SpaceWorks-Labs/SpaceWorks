from django.utils.translation import gettext
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings

from apps.accounts.models import User
from apps.accounts.services_refresh_tokens import rotate_refresh_token
from apps.accounts.tokens import SpaceWorksRefreshToken, validate_auth_generation


VERIFICATION_ONLY_SURFACE = "verification_only"
DEVICE_REFRESH_CLAIMS = ("device_grant_id", "device_family_id")


class SpaceWorksTokenRefreshSerializer(TokenRefreshSerializer):
    token_class = SpaceWorksRefreshToken

    def validate(self, attrs):
        def validate_token(refresh):
            if any(claim in refresh.payload for claim in DEVICE_REFRESH_CLAIMS):
                raise AuthenticationFailed(
                    gettext("Device refresh tokens must use the device refresh endpoint."),
                    code="device_refresh_wrong_endpoint",
                )
            validate_auth_generation(refresh)
            user_id = refresh.payload.get(api_settings.USER_ID_CLAIM)
            if not user_id:
                return None
            try:
                user = User.objects.get(
                    **{api_settings.USER_ID_FIELD: user_id}
                )
            except User.DoesNotExist as exc:
                raise AuthenticationFailed(
                    self.error_messages["no_active_account"],
                    code="no_active_account",
                ) from exc
            if not api_settings.USER_AUTHENTICATION_RULE(user):
                raise AuthenticationFailed(
                    self.error_messages["no_active_account"],
                    code="no_active_account",
                )
            if user.is_tenant_dump_stub:
                raise AuthenticationFailed(
                    self.error_messages["no_active_account"],
                    code="no_active_account",
                )
            from apps.accounts.surface_policy import validate_account_token
            validate_account_token(user, refresh)
            from apps.accounts.session_issuance import validate_session_generation
            validate_session_generation(user, refresh)
            from apps.accounts.session_context import validate_context
            requested = self.context.get("session_context")
            if requested is not None:
                validate_context(refresh, requested)
            from apps.accounts.mfa_policy import assert_verified
            assert_verified(user, refresh)
            from apps.accounts.web_sessions import validate_session
            validate_session(user, refresh, lock=True)
            return user

        def mint_replacement(refresh, _user):
            from apps.accounts.mfa_policy import restore_proof, stamp_claims
            restore_proof(_user, refresh)
            stamp_claims(_user, refresh)
            previous_iat = refresh.get("iat")
            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()
            from apps.accounts.staff_session_policy import stamp_rotated
            stamp_rotated(_user, refresh, previous_iat)
            from apps.accounts.web_sessions import extend_session
            extend_session(_user, refresh)
            refresh.outstand()
            from apps.accounts.serializers_payload import user_payload
            data = {"access": str(refresh.access_token),
                    "user": user_payload(_user, request=self.context.get("request"),
                                         session_authority=refresh["surface"])}
            data["refresh"] = str(refresh)
            return data

        return rotate_refresh_token(
            attrs["refresh"],
            token_class=self.token_class,
            validate=validate_token,
            mint=mint_replacement,
        )
