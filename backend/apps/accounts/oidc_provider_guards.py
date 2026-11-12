"""What an edit to a configured OIDC provider may not do (shared by /control/ and the web console).

1. **Never re-point linked sign-ins.** A linked identity is stored as ``oidc:<slug>`` plus the
   provider's ``sub``. Changing the slug orphans every one of them; changing the issuer is worse:
   a ``sub`` is only unique per issuer, so a person at the NEW identity server whose ``sub``
   happens to equal a linked one would be signed straight into someone else's account. Once
   anyone has linked the provider, its slug and issuer are fixed -- add a new provider instead.
2. **Never strand anyone.** Disabling (or blanking) a provider that is somebody's only way in is
   refused through the same complete-state check the login-method switches use.
"""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext

from apps.accounts.models_oidc import enabled_providers, provider_key
from apps.accounts.models_social import SocialIdentity


def _available(row):
    return row is not None and row.is_configured


def oidc_change_refusal(stored, proposed):
    """A refusal message for changing ``stored`` into ``proposed`` (unsaved), or None.

    ``stored`` is None for a new provider, which can strand nobody and re-point nothing.
    """
    if stored is None:
        return None
    old_key = provider_key(stored.slug)
    linked = SocialIdentity.objects.filter(provider=old_key).exists()
    if linked and (proposed.slug != stored.slug or proposed.issuer != stored.issuer):
        return gettext("People have already linked this provider, so its slug and issuer cannot change. "
                       "Add a new provider for a different identity server.")
    if not linked or not _available(stored) or _available(proposed):
        return None
    from apps.accounts.login_methods_validation import validate_login_methods
    from apps.accounts.models_login_methods import PlatformLoginMethods

    current_keys = {row.provider_key for row in enabled_providers()}
    policy = PlatformLoginMethods.load()
    try:
        validate_login_methods(policy, current=policy, oidc_keys=current_keys - {old_key},
                               current_oidc_keys=current_keys)
    except ValidationError as exc:
        return "; ".join(exc.messages)
    return None


def proposed_row(stored, values):
    """An unsaved copy of ``stored`` with ``values`` applied, for `oidc_change_refusal`."""
    from apps.accounts.models_oidc import OidcProvider

    fields = {field.name: getattr(stored, field.name) for field in OidcProvider._meta.concrete_fields}
    fields.update(values)
    return OidcProvider(**fields)
