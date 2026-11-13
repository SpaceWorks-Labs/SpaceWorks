"""Link GitHub or a configured OIDC provider to the signed-in person (browser only).

Reuses the sign-in machinery end to end — the single-use attempt ledger, origin-bound
redirect, PKCE S256, GitHub's code exchange and the OIDC ID-token verification — with one
difference: the attempt's nonce digest is bound to the signed-in session (`link_binding`).
A link attempt therefore cannot be finished by the sign-in callback (which would mint a
session) or by any other session, and a sign-in attempt cannot be finished here. The link
itself is `resolve_social_identity(explicit_user=...)`, the same rule the Google/Apple link
route uses: an identity owned by another account, a second subject from the same provider,
walk-in and anonymous records are all refused there.
"""

from django.conf import settings

from apps.accounts.github_browser import github_settings, start_github_attempt
from apps.accounts.github_http import github_claims
from apps.accounts.login_methods import social_login_enabled
from apps.accounts.models_oidc import provider_for_slug, slug_from_provider_key
from apps.accounts.oidc_browser_attempts import consume_attempt, start_attempt
from apps.accounts.oidc_browser_http import OidcProviderUnavailable, discover, exchange_code
from apps.accounts.services_social_identity import SocialResolutionError, resolve_social_identity
from apps.accounts.social_oidc import verify_oidc_token
from apps.accounts.staff_identity import is_person


def link_binding(request):
    """The signed-in browser session this link belongs to, or a refusal.

    Staff/platform accounts and native device grants are refused (browser members only,
    like the ID-token link route's staff refusal), and so is a token with no session id,
    because then there is no session to bind the attempt to.
    """
    user = request.user
    token = getattr(request, "auth", None)
    sid = token.get("sid") if token is not None and hasattr(token, "get") else None
    if not is_person(user) or getattr(request, "device_grant", None) is not None or not sid:
        raise SocialResolutionError("social_invalid", 403)
    return f"{user.pk}:{sid}"


def start_github_link(request, *, redirect_uri, nonce):
    binding = link_binding(request)
    return start_github_attempt(request, github_settings(), redirect_uri=redirect_uri, nonce=nonce,
                                link_binding=binding)


def start_oidc_link(request, slug, *, redirect_uri):
    binding = link_binding(request)
    provider = provider_for_slug(slug)
    if provider is None or not social_login_enabled():
        raise SocialResolutionError("social_unavailable", 404)
    started = start_attempt(request, provider, discover(provider), redirect_uri=redirect_uri,
                            link_binding=binding)
    return {"authorization_url": started.authorization_url, "state": started.state, "nonce": started.nonce,
            "expires_in": settings.OIDC_ATTEMPT_TTL_SECONDS}


def finish_link(request, *, code, state, nonce):
    """Consume the session-bound attempt, verify the provider, link. Returns (provider, claims)."""
    attempt = consume_attempt(request, state=state, nonce=nonce, link_binding=link_binding(request))
    if attempt.provider == "github":
        claims = github_claims(github_settings(), attempt, code)
    else:
        slug = slug_from_provider_key(attempt.provider)
        provider = provider_for_slug(slug) if slug is not None else None
        if provider is None or not social_login_enabled():
            raise OidcProviderUnavailable()
        document = discover(provider)
        raw = exchange_code(provider, document, code=code, redirect_uri=attempt.redirect_uri,
                            code_verifier=attempt.code_verifier)
        claims = verify_oidc_token(raw, nonce=nonce, provider_row=provider)
    try:
        resolve_social_identity(provider=attempt.provider, claims=claims, surface="member",
                                explicit_user=request.user)
    except SocialResolutionError as exc:
        exc.provider = attempt.provider  # the attempt is spent: the caller audits the refusal
        raise
    return attempt.provider, claims
