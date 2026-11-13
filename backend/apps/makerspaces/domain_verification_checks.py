"""Domain-change helpers split out of `domain_verification` (re-exported there): passkey impact, the change cooldown
and the platform-managed check. None of them reads `is_self_host`, so patching it on the main module stays valid."""
from django.conf import settings
from django.utils import timezone

from apps.makerspaces.hosting import canonical_host


def passkey_only_accounts(makerspace) -> int:
    """People whose only second factor is a passkey on this space's custom-domain RP ID.

    A domain change strands their passkey sign-in on the old address (passkeys are bound
    to it); the passkey still counts as their factor, so nobody is downgraded to "no
    factor", but they need their password and recovery codes, or another factor, on the
    new address. Shown before a change so the operator can warn them first.
    """
    if not makerspace.frontend_domain:
        return 0
    from apps.accounts.models import User
    from apps.accounts.models_mfa import UserMFA
    from apps.accounts.models_webauthn import WebAuthnCredential
    from apps.accounts.passkeys.rp_id import rp_id_for_host
    rp_id = rp_id_for_host(canonical_host(makerspace.frontend_domain))
    on_domain = WebAuthnCredential.objects.filter(rp_id=rp_id).values("user_id")
    elsewhere = WebAuthnCredential.objects.exclude(rp_id=rp_id).values("user_id")
    totp = UserMFA.objects.filter(enabled_at__isnull=False).values("user_id")
    return User.objects.filter(pk__in=on_domain).exclude(pk__in=elsewhere).exclude(pk__in=totp).count()


def domain_change_cooldown_active(makerspace, normalized_domain) -> bool:
    cooldown_seconds = settings.DOMAIN_CHANGE_COOLDOWN_SECONDS
    return bool(
        cooldown_seconds > 0
        and makerspace is not None
        and normalized_domain != makerspace.frontend_domain
        and makerspace.frontend_domain_changed_at is not None
        and (timezone.now() - makerspace.frontend_domain_changed_at).total_seconds()
        < cooldown_seconds
    )


def _is_platform_managed(domain) -> bool:
    suffix = str(settings.PLATFORM_DOMAIN_SUFFIX or "").strip().lower()
    canonical = canonical_host(domain or "")
    if not suffix or not canonical:
        return False
    return canonical == suffix.lstrip(".") or canonical.endswith(suffix)
