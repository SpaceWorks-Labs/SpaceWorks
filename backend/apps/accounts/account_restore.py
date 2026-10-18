"""Archive recovery changes identity availability, never revoked authority."""

import hmac

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.accounts.password_reset_crypto import _hmac
from apps.accounts.principal_guards import is_anonymous_requester
from apps.audit import services as audit


def recovery_eligible(user):
    """The same authority exclusions apply to reset issuance and archive recovery."""
    return bool(user and user.account_kind == User.AccountKind.MEMBER
                and user.retired_at is None and not user.is_tenant_dump_stub and not user.is_walk_in
                and not is_anonymous_requester(user)
                and not (user.is_superuser or user.role == User.Role.SUPERADMIN)
                and user.access_status == User.AccessStatus.ACTIVE)


def restorable(user, *, now=None):
    now = now or timezone.now()
    return bool(recovery_eligible(user) and user.deletion_requested_at
                and user.deletion_purge_after and now < user.deletion_purge_after
                and not user.purge_started_at and not user.account_purged_at)


def identifier_fingerprint(user):
    identities = list(user.social_identities.order_by("pk").values_list("pk", "provider", "provider_sub"))
    return _hmac(f"account-restore:v1:{user.pk}:{user.email.strip().lower()}:"
                 f"{user.account_kind}:{user.credential_generation}:{user.account_restored_at}:"
                 f"{user.phone_e164}:{user.email_verified_at}:{user.phone_verified_at}:"
                 f"{user.deletion_requested_at}:{user.password}:{identities}")


def matches(user, fingerprint):
    return bool(restorable(user) and hmac.compare_digest(identifier_fingerprint(user), fingerprint))


def restore_locked(user, *, fingerprint, new_password="", social=False):
    """Caller holds User through commit; purge commits its fence under that same lock."""
    if not matches(user, fingerprint):
        raise ValidationError({"detail": "Invalid or expired restore proof."})
    if social:
        if user.email or user.phone_e164:
            raise ValidationError({"detail": "Use email or phone recovery for this account."})
    else:
        from apps.accounts.services_password_reset import validate_recovery_password
        from django.core.exceptions import ValidationError as PasswordError
        try:
            validate_recovery_password(new_password, user)
        except PasswordError as exc:
            raise ValidationError({"new_password": list(exc.messages)}) from exc
        user.set_password(new_password)
    from apps.accounts.models_account_purge import AccountPurgeObject, AccountPurgeProgress
    # A fence proves none of these could have run. Do not delete completed work.
    AccountPurgeProgress.objects.filter(user=user, done_at__isnull=True).delete()
    AccountPurgeObject.objects.filter(user=user, deleted_at__isnull=True, attempts=0,
                                    quota_released_at__isnull=True).delete()
    user.deletion_requested_at = None
    user.deletion_purge_after = None
    user.account_restored_at = timezone.now()
    user.deletion_email_ciphertext = ""
    user.deletion_username = ""
    user.is_active = True
    user.credential_generation += 1
    user.must_change_password = False
    user.save(update_fields=["deletion_requested_at", "deletion_purge_after", "is_active", "password",
                             "must_change_password", "deletion_email_ciphertext", "deletion_username", "account_restored_at",
                             "credential_generation"])
    audit.record(user, "account.restored", target=user, meta={"method": "social" if social else "recovery"})
    return user


def restore_disclosure(user):
    if not recovery_eligible(user):
        return {"restorable": False, "restore_reason": "This account is not eligible for recovery."}
    if user.email or (user.phone_e164 and user.phone_verified_at):
        return {"restorable": True, "restore_reason": "Use password recovery or phone sign-in before the purge deadline."}
    if user.phone_e164:
        return {"restorable": False, "restore_reason": "Your phone is not verified and no email recovery address is available. "
                "This account cannot be restored after deletion."}
    providers = user.social_identities.values_list("provider", flat=True)
    possible = any(_provider_available(key) for key in providers)
    return {"restorable": possible, "restore_reason": (
        "Recovery requires a fresh sign-in from your linked provider with a verified authentication time. "
        "If it cannot supply that proof, recovery is unavailable; deletion removes your second factors."
        if possible else "Your linked provider cannot prove fresh authentication and no recovery second factor remains. "
        "This account cannot be restored after deletion.")}


def _provider_available(key):
    from apps.accounts.login_methods import provider_login_enabled
    from apps.accounts.models_oidc import provider_for_slug
    from apps.accounts.models_social import PlatformSocialAuthSettings
    from apps.accounts.social_lockout import provider_credentials_configured
    if not provider_login_enabled(key):
        return False
    if key.startswith("oidc:"):
        return provider_for_slug(key[5:]) is not None
    return key in {"apple", "google"} and provider_credentials_configured(
        PlatformSocialAuthSettings.objects.filter(pk=1).first(), key)
