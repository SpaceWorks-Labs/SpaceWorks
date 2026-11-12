"""Native GitHub sign-in: an authorization-code + PKCE exchange bound to an attested device.

GitHub issues no ID token, so the Google/Apple/OIDC native exchange (an ID token checked
against a nonce) cannot carry it. Decision 358 A:

* the app makes the PKCE pair; only the S256 ``code_challenge`` reaches the server at start;
* the redirect URI is fixed server-side: ``PUBLIC_APP_BASE_URL`` + ``NATIVE_GITHUB_CALLBACK_PATH``,
  an HTTPS universal link / Android App Link the association files claim (never a custom
  URL scheme, which any app could register);
* the ``state`` is a one-time row in the SAME social nonce ledger the other native providers
  use (`SocialLoginNonce`, provider ``github``, delivery ``device``), anchored to the caller's
  grant or an unspent attestation challenge, and its digest binds the code challenge -- so a
  replayed state, another device's state and a wrong ``code_verifier`` all miss;
* GitHub verifies the same verifier against the challenge when the code is redeemed.

Switches, ownership verification (verified primary email) and account linking are the web
flow's own: `github_browser.github_settings`, `github_http.github_claims` and
`resolve_social_identity`.
"""

import base64
import hashlib
import secrets
from datetime import timedelta
from types import SimpleNamespace
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.utils import timezone

from apps.accounts.github_browser import GithubUnavailable, github_settings
from apps.accounts.models_social import (
    SocialDelivery, SocialLoginNonce, SocialProvider, SocialSurface,
)
from apps.accounts.social_nonces import consume_social_nonce, device_anchor, nonce_digest
from apps.integrations.mobile_link_contract import NATIVE_GITHUB_CALLBACK_PATH

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_SCOPE = "read:user user:email"


def native_redirect_uri():
    """The one redirect GitHub may send a native code to: the primary web host's app link."""
    base = (settings.PUBLIC_APP_BASE_URL or "").rstrip("/")
    parts = urlsplit(base)
    local = parts.hostname in {"localhost", "127.0.0.1", "::1"}
    if not parts.hostname or parts.path or (parts.scheme != "https" and not (local and parts.scheme == "http")):
        raise GithubUnavailable()
    return f"{base}{NATIVE_GITHUB_CALLBACK_PATH}"


def s256(verifier):
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def _bound(state, code_challenge):
    # The state alone never matches a row: the PKCE challenge is part of the digest.
    return f"github-native:v1\0{state}\0{code_challenge}"


def start_native_github(request, *, client_platform, code_challenge, challenge=None):
    """Mint the one-time state and the GitHub authorize URL the app opens."""
    row = github_settings()
    redirect_uri = native_redirect_uri()
    grant, attestation_challenge = device_anchor(request, client_platform, challenge)
    state = secrets.token_urlsafe(48)
    ttl = settings.OIDC_ATTEMPT_TTL_SECONDS
    SocialLoginNonce.objects.create(
        provider=SocialProvider.GITHUB, surface=SocialSurface.MEMBER, delivery=SocialDelivery.DEVICE,
        client_platform=client_platform, nonce_digest=nonce_digest(_bound(state, code_challenge)),
        origin="", device_grant=grant, attestation_challenge=attestation_challenge,
        expires_at=timezone.now() + timedelta(seconds=ttl),
    )
    query = urlencode({
        "client_id": row.github_client_id, "redirect_uri": redirect_uri, "state": state,
        "scope": GITHUB_SCOPE, "code_challenge": code_challenge, "code_challenge_method": "S256",
    })
    return {"authorization_url": f"{GITHUB_AUTHORIZE_URL}?{query}", "state": state,
            "redirect_uri": redirect_uri, "expires_in": ttl}


def consume_native_github(request, *, state, code_verifier, client_platform, challenge=None):
    """Burn the state row (single use, device-bound) and return ``(row, attestation_challenge,
    attempt)``; ``attempt`` carries what `github_claims` redeems the code with."""
    raw = _bound(state, s256(code_verifier))
    row, attestation_challenge = consume_social_nonce(
        request, raw=raw, provider=SocialProvider.GITHUB, surface=SocialSurface.MEMBER,
        delivery=SocialDelivery.DEVICE, client_platform=client_platform, raw_challenge=challenge,
    )
    attempt = SimpleNamespace(redirect_uri=native_redirect_uri(), code_verifier=code_verifier)
    return row, attestation_challenge, attempt
