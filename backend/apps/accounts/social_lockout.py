"""Refuse to disable a social provider that is somebody's only way in (plan A6).

`unlink_social_identity` already protects a user who removes their *own* last
credential. The platform-wide twin had no guard at all: a superadmin clearing Google or
Apple in `/control/` silently locks out every account created through that provider
that never set a password. Those users cannot even use forgot-password -- they have no
usable password to reset, so the one recovery flow that exists will not help them.

So the check runs on the way in, names the number of affected accounts, and points at
the remedy rather than just refusing.
"""

from django.db.models import Exists, OuterRef

from apps.accounts.models import User
from apps.accounts.models_social import SocialIdentity, SocialProvider
from apps.accounts.staff_identity import person_q

GOOGLE_FIELDS = ("google_web_client_id", "google_ios_client_id", "google_android_client_id")
CONFIG_FIELDS = (*GOOGLE_FIELDS, "apple_service_id", "apple_native_app_ids",
                 "github_client_id", "github_client_secret")


def provider_configured(settings_row, provider):
    from apps.accounts.login_methods import provider_login_enabled

    return provider_login_enabled(provider) and provider_credentials_configured(settings_row, provider)


def provider_credentials_configured(settings_row, provider):
    """Whether `provider` is resolvable at all with these settings."""
    if settings_row is None:
        return False
    if provider == SocialProvider.GOOGLE:
        return any(
            (getattr(settings_row, field, "") or "").strip() for field in GOOGLE_FIELDS
        )
    if provider == SocialProvider.GITHUB:
        return bool(settings_row.github_client_id.strip() and settings_row.github_client_secret_set)
    if provider == SocialProvider.APPLE:
        return bool(
            settings_row.apple_service_id.strip() or settings_row.apple_native_app_ids
        )
    return False


def users_locked_out_by_disabling(provider):
    """Active users whose ONLY credential is `provider`.

    "Only credential" means an identity for this provider, no identity for any other
    provider, and no usable password. Inactive accounts are excluded: they cannot sign
    in either way, so they are not a reason to block an administrative change.

    A superadmin's other identity only counts when it is staff-capable: GitHub issues
    member sessions, so it cannot get a superadmin back into the console.

    `has_usable_password()` is not expressible in SQL (it inspects the hash prefix), so
    the query narrows to users with this provider and the final check runs in Python.
    """
    other_identity = SocialIdentity.objects.filter(user=OuterRef("pk")).exclude(
        provider=provider
    )
    candidates = (
        User.objects.filter(person_q(), is_active=True, social_identities__provider=provider)
        .annotate(
            has_other_identity=Exists(other_identity),
            has_staff_identity=Exists(other_identity.exclude(provider=SocialProvider.GITHUB)),
        )
        .distinct()
    )
    stranded = []
    for user in candidates:
        superadmin = user.is_superuser or user.role == User.Role.SUPERADMIN
        rescued = user.has_staff_identity if superadmin else user.has_other_identity
        if not rescued and not user.has_usable_password():
            stranded.append(user)
    return stranded


def disabling_lockout_message(stored, incoming):
    """The refusal for an edit that would strand accounts, or None when it is safe.

    One predicate for both write surfaces -- the `/control/` form and the staff-console
    `PATCH /admin/platform/social-auth-settings` -- so the API cannot quietly do what the
    form refuses. Only the OFF direction is checked: configuring a provider strands no one.
    """
    from django.core.exceptions import ValidationError

    from apps.accounts.login_methods_validation import validate_login_methods
    from apps.accounts.models_login_methods import PlatformLoginMethods

    if not any(provider_credentials_configured(stored, provider)
               and not provider_credentials_configured(incoming, provider)
               for provider in SocialProvider):
        return None
    # The whole incoming state at once, so clearing two providers in one edit cannot let
    # each count the other as the rescue; before/after, so an account that is already
    # stranded does not block an unrelated edit.
    policy = PlatformLoginMethods.load()
    try:
        validate_login_methods(policy, social_settings=incoming,
                               current=policy, current_social_settings=stored)
    except ValidationError as exc:
        return "; ".join(exc.messages)
    return None
