from django.db import transaction
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.models import User
from apps.accounts.tokens import SpaceWorksRefreshToken


VERIFICATION_ONLY_SURFACE = "verification_only"
DEVICE_REFRESH_CLAIMS = ("device_grant_id", "device_family_id")


from apps.accounts.serializers_payload import user_payload

class LoginSerializer(TokenObtainPairSerializer):
    """One password door for every person; the superadmin only from a platform origin.

    Release 2 dropped ``context``, ``makerspace`` and ``surface`` (one account per person):
    the account decides the session, and staff authority is resolved per request.
    """

    token_class = SpaceWorksRefreshToken

    def validate(self, attrs):
        # Django/axes records failed password attempts during authenticate(). Commit
        # that accounting before raising; rolling it back would disable lockout.
        failure = None
        with transaction.atomic():
            try:
                data = self._validate_credentials(attrs)
            except AuthenticationFailed as exc:
                failure = exc
        if failure is not None:
            raise failure
        return data

    def _validate_credentials(self, attrs):
        from apps.accounts.login_context import resolve_login
        request = self.context.get("request")
        candidate, surface = resolve_login(attrs, request)
        # Password reset holds this same account lock through credential change and
        # revocation. Old password verification cannot mint a post-reset session.
        candidate = User.objects.select_for_update(no_key=True).get(pk=candidate.pk)
        from rest_framework_simplejwt.serializers import TokenObtainSerializer
        data = TokenObtainSerializer.validate(self, attrs)
        if self.user.pk != candidate.pk:
            raise AuthenticationFailed(self.error_messages["no_active_account"], code="no_active_account")
        from apps.accounts.surface_policy import assert_surface
        assert_surface(self.user, surface, request)
        from apps.backup.recovery import assert_token_issuance_allowed
        assert_token_issuance_allowed(self.user)
        if (
            self.user.self_registered_at is not None
            and self.user.email_verified_at is None
        ):
            surface = VERIFICATION_ONLY_SURFACE

        from apps.accounts.mfa_policy import needs_challenge
        from apps.accounts.mfa_challenges import start
        from apps.accounts.mfa_sessions import context
        if needs_challenge(self.user):
            return start(self.user, context=context(request, surface=surface))
        refresh = self.token_class.for_user(self.user)
        refresh["surface"] = surface
        data["refresh"] = str(refresh)
        data["access"] = str(refresh.access_token)
        data["surface"] = surface
        data["user"] = user_payload(self.user, request=request, session_authority=surface)
        return data

