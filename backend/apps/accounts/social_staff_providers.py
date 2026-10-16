"""Identity providers that can issue staff sessions, shared by lockout guards."""

from django.db.models import Q


def staff_capable_provider_filter():
    # GitHub and phone issue member sessions only; neither can rescue a superadmin.
    return Q(provider__in=("google", "apple")) | Q(provider__startswith="oidc:")


def surviving_identities(user, identities):
    from apps.accounts.login_methods_validation import available_providers
    from apps.accounts.models_login_methods import PlatformLoginMethods

    identities = identities.filter(provider__in=available_providers(PlatformLoginMethods.load()))
    if user.is_superuser or user.role == "superadmin":
        return identities.filter(staff_capable_provider_filter())
    return identities
