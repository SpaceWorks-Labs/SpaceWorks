"""Social provider verification and typed error responses shared by both surfaces."""

from rest_framework.response import Response
from apps.accounts import audit_events
from apps.accounts.services_social_login import social_audit_meta
from apps.accounts.social_nonces import SocialAuthUnavailable
from apps.accounts.models_oidc import provider_for_slug, slug_from_provider_key
from apps.accounts.models_social import SocialProvider


def _error(code, status_code):
    messages = {
        "social_unavailable": "Social sign-in is unavailable.",
        "social_invalid": "Social sign-in could not be verified.",
        "account_link_required": "Sign in with an existing credential to link this account.",
        "staff_access_required": "An existing staff account is required.",
        "identity_conflict": "That provider identity is linked to another account.",
        "provider_already_linked": "A different identity from that provider is already linked.",
        "last_credential": "Add another sign-in method before removing this one.",
        "identity_not_found": "That provider is not linked.",
        "access_denied": "Account access is restricted.",
        "registration_disabled": "Account registration is not available.",
        "social_device_restart_required": "Restart device sign-in with a fresh nonce and attestation challenge.",
    }
    return Response({"detail": messages.get(code, messages["social_invalid"]), "code": code}, status=status_code)


def _verify(provider, raw_token, nonce, audience):
    slug = slug_from_provider_key(provider)
    if slug is not None:
        from apps.accounts.social_oidc import verify_oidc_token

        row = provider_for_slug(slug)
        if row is None:
            raise SocialAuthUnavailable
        return verify_oidc_token(raw_token, nonce=nonce, provider_row=row)
    if provider == SocialProvider.GOOGLE:
        from apps.accounts.social_google import verify_google_token
        return verify_google_token(raw_token, nonce=nonce, audience=audience)
    from apps.accounts.social_apple import verify_apple_token
    return verify_apple_token(raw_token, nonce=nonce, audience=audience)


def _audit_failure(provider, reason, request=None):
    audit_events.record_auth_event(None, "auth.social_login_failed", meta={"provider": provider, "reason": reason})
    if request is not None:  # S-B: a refused social sign-in feeds the failure counters
        from apps.accounts.security_signals import send_login_refused
        send_login_refused(request, "", f"social_{reason}")


def _store_apple(provider, user, claims, data):
    if provider == SocialProvider.APPLE:
        from apps.accounts.apple_credentials import store_refresh_credential
        store_refresh_credential(user, claims, data.get("authorization_code", ""),
                                 data.get("redirect_uri", "") if data["delivery"] == "web" else "")


def _challenged(provider, user, outcome, claims, data, challenge):
    """The provider proved the person; their mandatory second factor comes next (#62)."""
    audit_events.record_auth_event(user, "auth.social_login_succeeded", target=user,
                                   meta=social_audit_meta(provider, outcome, claims["sub"]))
    _store_apple(provider, user, claims, data)
    response = Response(challenge)
    response["Cache-Control"] = "no-store"
    return response
