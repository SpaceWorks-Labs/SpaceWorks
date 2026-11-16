"""Validate the complete proposed policy, including simultaneous provider removals."""

from django.utils.translation import gettext
from django.core.exceptions import ValidationError
from django.db.models import Q

from apps.accounts.credential_inventory import phone_ready, ways_in
from apps.accounts.models import User
from apps.accounts.models_oidc import enabled_providers
from apps.accounts.models_social import PlatformSocialAuthSettings, SocialProvider
from apps.accounts.staff_identity import is_person, person_q


def available_providers(proposed, *, social_settings=None, oidc_keys=None):
    """Provider keys that can sign someone in under ``proposed``. ``oidc_keys`` replaces the
    stored enabled OIDC providers, so a provider edit can be judged before it is saved."""
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
    if oidc_keys is None:
        oidc_keys = {row.provider_key for row in enabled_providers()}
    providers.update(oidc_keys)
    return providers


def _stranded(policy, candidates, *, social_settings=None, oidc_keys=None):
    """(superadmin ids, other ids) with no way in under `policy`.

    A way in is a password, a surviving provider, a verified phone or a passkey
    (`credential_inventory`), so switching phone sign-in or passkeys off is judged exactly
    like switching a provider off.
    """
    available = available_providers(policy, social_settings=social_settings, oidc_keys=oidc_keys)
    phone_ok = phone_ready(policy)
    admins, users = set(), set()
    for user in candidates:
        # Member switches never control privileged password sign-in. Legacy
        # social links cannot count as staff/platform recovery credentials.
        if not is_person(user):
            continue
        if not ways_in(user, policy, available, phone_ok=phone_ok):
            users.add(user.pk)
    return admins, users


def _candidates():
    """Live people holding any credential a switch can take away besides a password.

    A password-only account is governed by the member password switch alone: switching it off
    for members is the operator's documented choice (staff keep their password door).
    """
    holds = (Q(social_identities__isnull=False) | Q(webauthn_credentials__isnull=False)
             | (~Q(phone_e164="") & Q(phone_verified_at__isnull=False)))
    return list(User.objects.filter(person_q(), holds, retired_at__isnull=True, is_active=True)
                .distinct().prefetch_related("social_identities"))


def validate_login_methods(proposed, *, current=None, social_settings=None,
                           current_social_settings=None, oidc_keys=None, current_oidc_keys=None):
    """Protect member credentials without applying member switches to staff.

    Only accounts the change NEWLY strands are refused: an account that already has no way
    in under `current` (e.g. a superadmin created without a password) must not block an
    unrelated edit. `current=None` (first install) judges the proposed state alone.
    """
    candidates = _candidates()
    admins, users = _stranded(proposed, candidates, social_settings=social_settings, oidc_keys=oidc_keys)
    if current is not None:
        before_admins, before_users = _stranded(
            current, candidates, social_settings=current_social_settings, oidc_keys=current_oidc_keys,
        )
        admins, users = admins - before_admins, users - before_users
    stranded_users = len(users)
    if stranded_users:
        raise ValidationError(
            gettext('This change would lock out {stranded_users} account(s) with no remaining available credential. Set a usable password with password sign-in enabled, or link a configured provider that will remain enabled first.').format(stranded_users=stranded_users)
        )
