"""Provider-specific freshness rules over the existing verified-token parsers."""

from types import SimpleNamespace

from django.utils import timezone

from apps.accounts.social_jwt import SocialTokenError, SocialProviderUnavailable


def freshness(provider, auth_time):
    if provider == "github":
        # The OAuth user endpoint has no authentication-time assertion.
        return False
    now = timezone.now().timestamp()
    fresh = (not isinstance(auth_time, bool) and isinstance(auth_time, (int, float))
             and now - 300 <= auth_time <= now)
    if provider == "apple" and not fresh:
        raise SocialTokenError()
    # OIDC omission can be supplemented, but a supplied stale/invalid timestamp
    # contradicts the mandatory prompt=login request and is refused.
    if provider.startswith("oidc:") and auth_time is not None and not fresh:
        raise SocialTokenError()
    return fresh


def provider_claims(request, intent, *, nonce, id_token, code):
    from apps.accounts.reauthentication_intents import _provider, discover, exchange_code
    from apps.makerspaces.secrets import decrypt_value

    key = intent.context["provider"]
    provider, _, _ = _provider(key)
    if key == "github":
        from apps.accounts.github_browser import GithubRejected, GithubUnavailable
        from apps.accounts.github_http import github_claims
        attempt = SimpleNamespace(redirect_uri=intent.context["redirect_uri"],
                                  code_verifier=decrypt_value(intent.pending_secret))
        try:
            return github_claims(provider, attempt, code)
        except GithubRejected as exc:
            raise SocialTokenError() from exc
        except GithubUnavailable as exc:
            raise SocialProviderUnavailable() from exc
    if key.startswith("oidc:"):
        from apps.accounts.social_oidc import verify_oidc_token
        token = exchange_code(provider, discover(provider), code=code,
                              redirect_uri=intent.context["redirect_uri"],
                              code_verifier=decrypt_value(intent.pending_secret))
        return verify_oidc_token(token, nonce=nonce, provider_row=provider)
    grant = getattr(request, "device_grant", None)
    if getattr(request, "auth", None) and request.auth.get("device_grant_id") and grant is None:
        from apps.accounts.models_devices import DeviceGrant
        grant = DeviceGrant.objects.get(pk=request.auth["device_grant_id"], user=request.user)
    platform = ("ios" if grant.platform == "apple" else "android") if grant else "web"
    audience = provider.client_id(key, platform)
    if key == "apple" and grant:
        audience = grant.app_id if grant.app_id in provider.apple_native_app_ids else ""
    if not audience:
        raise SocialTokenError()
    if key == "google":
        from apps.accounts.social_google import verify_google_token
        return verify_google_token(id_token, nonce=nonce, audience=audience)
    if key == "apple":
        from apps.accounts.social_apple import verify_apple_token
        return verify_apple_token(id_token, nonce=nonce, audience=audience)
    raise SocialTokenError()
