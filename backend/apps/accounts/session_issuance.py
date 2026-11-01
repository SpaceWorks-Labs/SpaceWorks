"""Serialize session issuance with account departure and credential changes."""

import hmac

from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.models import User
from apps.accounts.staff_identity import context_label


def validate_session_generation(user, token):
    if token.get("credential_generation") != user.credential_generation:
        raise AuthenticationFailed("Account credentials have changed. Sign in again.")


def lock_session_user(authenticated):
    """Caller holds an atomic block through minting.

    Authentication lock order is User -> registration/credential rows. Departure
    takes the same User lock before revoking credentials. NO KEY UPDATE permits
    concurrent FK references without lock upgrades. Keep the authenticated
    snapshot: reloading alone must not bless a password changed while we waited,
    or a sign-in begun before departure and completed after account restoration.
    """
    user = User.objects.select_for_update(no_key=True).filter(pk=authenticated.pk).first()
    if (
        user is None or user.is_tenant_dump_stub or not user.is_active
        or user.retired_at is not None
        or user.deletion_requested_at is not None
        or user.access_status != User.AccessStatus.ACTIVE
        or context_label(user) != context_label(authenticated)
        or user.merged_into_id is not None
        or user.credential_generation != authenticated.credential_generation
        or not hmac.compare_digest(user.password, authenticated.password)
        or user.account_restored_at != authenticated.account_restored_at
    ):
        raise AuthenticationFailed("Account or credentials are no longer available. Sign in again.")
    for attr in ("_mfa_verified_version", "_mfa_provider_verified", "_mfa_source"):
        if hasattr(authenticated, attr):
            setattr(user, attr, getattr(authenticated, attr))
    return user
