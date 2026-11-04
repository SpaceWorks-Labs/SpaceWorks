"""Invalidate account bearers and second-factor secrets in the departure transaction."""

from django.apps import apps

from apps.accounts.models_password_reset import PasswordResetEnvelope
from apps.accounts.models_mfa import UserMFA
from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.backup.capture_managers import every_row


def revoke(user, now):
    from apps.accounts.account_kind_guards import require_member_account
    from apps.accounts.credential_revocation_helpers import revoke_authentication, revoke_pending_proofs
    require_member_account(user)
    user.credential_generation += 1
    user.save(update_fields=["credential_generation"])
    revoke_authentication(user, now=now, revoke_invitations=False)
    revoke_pending_proofs(user, now=now)
    ReauthenticationSession.objects.filter(user=user).delete()
    PasswordResetEnvelope.objects.filter(user=user).update(
        digest_is_live=False, consumed_at=now, status="discarded", terminal_at=now,
    )
    # Deployments using DRF personal API tokens must invalidate those too. Tenant
    # HMAC ApiClients are application credentials, not personal account tokens.
    if apps.is_installed("rest_framework.authtoken"):
        every_row(apps.get_model("authtoken.Token")).filter(user=user).delete()
    try:
        push = apps.get_model("integrations.PushDevice")
    except LookupError:
        push = None
    if push is not None:
        every_row(push).filter(user=user, active=True).update(active=False, invalidated_at=now)
    UserMFA.objects.filter(user=user).delete()
