"""Advertise usable identity proofs; email enrollment is never recent auth."""


def methods(user):
    from apps.accounts.models_mfa import UserMFA
    from apps.accounts.reauthentication_factors import second_factor
    from apps.accounts.reauthentication_phone import available
    from apps.accounts.models_oidc import provider_for_slug
    from apps.accounts.models_social import PlatformSocialAuthSettings
    from apps.accounts.social_lockout import provider_configured
    from apps.accounts.login_methods import social_login_enabled

    result = ["password"] if user.has_usable_password() else []
    if UserMFA.objects.filter(user=user, enabled_at__isnull=False).exists():
        result.append("totp")
    if available(user):
        result.append("phone")
    if social_login_enabled():
        settings = PlatformSocialAuthSettings.objects.filter(pk=1).first()
        factor = second_factor(user)
        for key in user.social_identities.order_by("provider").values_list("provider", flat=True):
            configured = (provider_for_slug(key[5:]) is not None if key.startswith("oidc:")
                          else provider_configured(settings, key))
            if configured and (key != "github" or factor):
                result.append(key)
    return result
