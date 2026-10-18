"""Project-owned JWT classes bound to one deployment generation."""

from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from django.db import transaction


def current_auth_generation():
    from apps.backup.models import DeploymentRecoveryState

    return str(DeploymentRecoveryState.load().auth_generation)


def validate_auth_generation(token):
    from rest_framework_simplejwt.exceptions import AuthenticationFailed

    if str(token.get("auth_generation") or "") != current_auth_generation():
        raise AuthenticationFailed(
            "This session belongs to a different authentication generation.",
            code="auth_generation_mismatch",
        )


class _GenerationBoundToken:
    def verify(self, *args, **kwargs):
        super().verify(*args, **kwargs)
        validate_auth_generation(self)


class SpaceWorksAccessToken(_GenerationBoundToken, AccessToken):
    """Bearer token accepted only by the deployment generation that minted it."""


class SpaceWorksRefreshToken(_GenerationBoundToken, RefreshToken):
    access_token_class = SpaceWorksAccessToken

    @classmethod
    @transaction.atomic
    def for_user(cls, user, *, web_session=True):
        # A credential change also locks User. Hold that same lock through both
        # verification and minting so an unenrolled login cannot pick up the new
        # credential's version between these reads without proving its factor.
        from apps.accounts.session_issuance import lock_session_user
        user = lock_session_user(user)
        from apps.accounts.mfa_policy import assert_verified, credential, source_for
        assert_verified(user)
        token = super().for_user(user)
        token["kind"] = user.account_kind
        token["credential_generation"] = user.credential_generation
        token["surface"] = {"member": "member", "staff": "staff_api", "platform": "platform"}[user.account_kind]
        if user.account_kind == "staff":
            token["makerspace"] = user.staff_makerspace_id
        from apps.accounts.surface_policy import assert_surface
        assert_surface(user, token["surface"])
        token["mfa_source"] = source_for(user)
        row = credential(user)
        if row:
            token["mfa_version"] = str(row.version)
        token["auth_generation"] = current_auth_generation()
        if web_session:
            from apps.accounts.web_sessions import create_session

            create_session(user, token)
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
        OutstandingToken.objects.filter(jti=token["jti"], user=user).update(token=str(token))
        return token
