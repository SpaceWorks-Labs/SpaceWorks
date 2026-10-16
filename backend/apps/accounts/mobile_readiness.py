"""Read-only configuration readiness. Never decrypt secrets or probe providers."""

from django.core.exceptions import ValidationError

from apps.accounts.attestation import AttestationUnavailable, configured_app, readiness_mode
from apps.accounts.login_methods import provider_login_enabled, social_login_enabled
from apps.accounts.mobile_associations import primary_frontend_hosts
from apps.accounts.models_oidc import OidcProvider
from apps.accounts.models_social import PlatformSocialAuthSettings
from apps.accounts.native_app_identity import (
    eligible_registrations, registration_is_eligible, registration_signing_identities,
)
from apps.accounts.services_device_tokens import mobile_grant_creation_enabled
from apps.integrations.models_push import PlatformPushSettings
from apps.makerspaces.hosting import verified_frontend_domains


def item(ready, hint):
    return {"ready": bool(ready), "hint": hint}


def registration_readiness(row, *, social, push, mobile_enabled, has_hosts):
    try:
        identities = registration_signing_identities(row)
    except ValidationError:
        identities = []
    login = {"registration": item(registration_is_eligible(row) and bool(identities),
                                  "Approved global registration with valid distribution signers / App ID Prefix.")}
    try:
        identity = configured_app(row.platform, row.verifier_config_key, row.environment, registration=row)
        mode = readiness_mode(row.platform, identity)
        effective = True
    except AttestationUnavailable:
        mode, effective = "unavailable", False
    mode_hints = {
        "external": "HTTPS external verifier configured; only the first signer is supported.",
        "in_process": "In-process verification configured (Apple prefix / Play Integrity service account).",
        "development_insecure": "Development bypass only; never production ready.",
        "unavailable": "Configure a valid App ID Prefix, Play Integrity service account or HTTPS verifier and token.",
    }
    login["attestation"] = item(effective, mode_hints[mode])
    login["mobile"] = item(mobile_enabled, "Enable the deployment mobile module to mint grants.")
    if social_login_enabled():
        if provider_login_enabled("google"):
            client_field = "google_ios_client_id" if row.platform == "apple" else "google_android_client_id"
            login["google"] = item(social and getattr(social, client_field),
                                   "Set this platform's native Google client ID in Platform social auth settings.")
        if row.platform == "apple" and provider_login_enabled("apple"):
            login["apple"] = item(social and row.app_id in (social.apple_native_app_ids or []),
                                  "Include this bundle ID in Apple native app IDs in Platform social auth settings.")
        for provider in OidcProvider.objects.filter(is_enabled=True).order_by("pk"):
            login[f"oidc:{provider.slug}"] = item(provider.is_configured,
                "Enabled OIDC provider needs its client ID, HTTPS issuer and JWKS URL.")
    if row.platform == "android":
        push_ready = bool(push and push.fcm_configured)
        push_hint = "Set the FCM service account in Platform push settings."
    else:
        push_ready = bool(push and push.apns_configured and push.apns_topic == row.app_id)
        push_hint = "Set APNs key, team and key ID; topic must equal this registration's bundle ID."
    optional = {
        "push": item(push_ready, push_hint),
        "apple_revocation": item(social and social.apple_team_id and social.apple_key_id and social.apple_private_key,
                                 "Optional Sign in with Apple revocation key: team, key ID and private key in social settings."),
        "associations": item(row.environment == "production" and identities and has_hosts,
                             "Association documents include valid production registrations on eligible frontend hosts."),
    }
    return {"hint": f"{row.app_id} ({row.environment})", "production": row.environment == "production",
            "login_ready": all(check["ready"] for check in login.values()),
            "login": login, "optional": optional}


def mobile_readiness():
    social = PlatformSocialAuthSettings.objects.filter(pk=1).first()
    push = PlatformPushSettings.objects.filter(pk=1).first()
    context = {"social": social, "push": push, "mobile_enabled": mobile_grant_creation_enabled(),
               "has_hosts": bool(primary_frontend_hosts() or verified_frontend_domains())}
    platforms = {"android": {"registrations": []}, "ios": {"registrations": []}}
    for row in eligible_registrations().order_by("platform", "environment", "app_id", "pk"):
        key = "ios" if row.platform == "apple" else row.platform
        if key in platforms:
            platforms[key]["registrations"].append(registration_readiness(row, **context))
    for platform in platforms.values():
        production = [row for row in platform["registrations"] if row["production"]]
        platform.update({"login_ready": bool(production) and all(row["login_ready"] for row in production),
                         "hint": "All production registrations must be ready; development registrations are listed separately."})
        for key in ("push", "apple_revocation", "associations"):
            platform[f"{key}_ready"] = bool(production) and all(row["optional"][key]["ready"] for row in production)
    return {"platforms": platforms}
