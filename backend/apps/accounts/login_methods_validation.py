"""Validate the complete proposed policy, including simultaneous provider removals."""

from django.core.exceptions import ValidationError
from django.db.models import Q

from apps.accounts.models import User
from apps.accounts.models_oidc import enabled_providers
from apps.accounts.models_social import PlatformSocialAuthSettings, SocialProvider


def available_providers(proposed, *, social_settings=None):
    from apps.accounts.social_lockout import provider_credentials_configured

    if not proposed.social_enabled:
        return set()
    if social_settings is None:
        social_settings = PlatformSocialAuthSettings.objects.filter(pk=1).first()
    providers = {
        str(provider) for provider in SocialProvider
        if getattr(proposed, f"{provider}_enabled", False)
        and provider_credentials_configured(social_settings, provider)
    }
    providers.update(row.provider_key for row in enabled_providers())
    return providers


def _stranded(policy, candidates, *, social_settings=None):
    """(superadmin ids, other ids) with no way in under `policy`."""
    available = available_providers(policy, social_settings=social_settings)
    admins, users = set(), set()
    for user in candidates:
        if policy.password_enabled and user.has_usable_password():
            continue
        surviving = {identity.provider for identity in user.social_identities.all()} & available
        if user.is_superuser or user.role == User.Role.SUPERADMIN:
            if not surviving - {"github"}:
                admins.add(user.pk)
        elif not surviving:
            users.add(user.pk)
    return admins, users


def validate_login_methods(proposed, *, current=None, social_settings=None,
                           current_social_settings=None):
    """Fail closed on writes; phone and GitHub cannot rescue a staff session.

    Only accounts the change NEWLY strands are refused: an account that already has no way
    in under `current` (e.g. a superadmin created without a password) must not block an
    unrelated edit. `current=None` (first install) judges the proposed state alone.
    """
    if not proposed.password_enabled and not proposed.social_enabled:
        raise ValidationError(
            "Password and social sign-in cannot both be off: phone sign-in issues "
            "member sessions only, so nobody could reach the staff console."
        )
    candidates = list(User.objects.filter(is_active=True).filter(
        Q(social_identities__isnull=False) | Q(is_superuser=True) | Q(role=User.Role.SUPERADMIN)
    ).distinct().prefetch_related("social_identities"))
    admins, users = _stranded(proposed, candidates, social_settings=social_settings)
    if current is not None:
        before_admins, before_users = _stranded(
            current, candidates, social_settings=current_social_settings
        )
        admins, users = admins - before_admins, users - before_users
    stranded_admins, stranded_users = len(admins), len(users)
    if stranded_admins:
        raise ValidationError(
            f"This change would lock out {stranded_admins} superadmin(s). Keep password "
            "sign-in with a usable password. Link a provider that is configured, enabled "
            "and staff-capable (Google, Apple or OIDC) first. Phone and GitHub are member-only."
        )
    if stranded_users:
        raise ValidationError(
            f"This change would lock out {stranded_users} account(s) with no remaining "
            "available credential. Set a usable password with password sign-in enabled, "
            "or link a configured provider that will remain enabled first."
        )
