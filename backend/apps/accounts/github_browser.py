"""Member-only GitHub OAuth attempts in the shared browser-attempt ledger."""

import base64
import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.login_methods import social_login_enabled
from apps.accounts.member_identity import member_login_allowed
from apps.accounts.models_oidc_browser import OidcBrowserAttempt
from apps.accounts.models_social import PlatformSocialAuthSettings
from apps.accounts.oidc_browser_attempts import OidcAttemptRejected, _digest, _valid_redirect, nonce_digest
from apps.accounts.social_lockout import provider_configured
from apps.accounts.social_nonces import request_origin
from apps.audit import services as audit
from apps.makerspaces.cors import member_origin_is_registered


class GithubUnavailable(Exception):
    pass


class GithubRejected(Exception):
    pass


def github_settings():
    if not social_login_enabled() or not member_login_allowed("github"):
        raise GithubUnavailable()
    row = PlatformSocialAuthSettings.objects.filter(pk=1).first()
    if not provider_configured(row, "github"):
        raise GithubUnavailable()
    return row


def start_github_attempt(request, row, *, redirect_uri, nonce, link_binding="", next_path=""):
    origin = request_origin(request)
    if not member_origin_is_registered(origin) or not _valid_redirect(redirect_uri, origin):
        raise OidcAttemptRejected()
    state = secrets.token_urlsafe(48)
    verifier = secrets.token_urlsafe(64)
    with transaction.atomic():
        attempt = OidcBrowserAttempt.objects.create(
            provider="github", state_digest=_digest("state", state),
            nonce_digest=nonce_digest(nonce, link_binding), code_verifier=verifier,
            redirect_uri=redirect_uri, origin=origin, next_path=next_path,
            expires_at=timezone.now() + timedelta(seconds=settings.OIDC_ATTEMPT_TTL_SECONDS),
        )
        # The event names describe the shared attempt ledger; provider distinguishes OAuth.
        audit.record(
            request.user if request.user.is_authenticated else None,
            "auth.oidc_browser_attempt_started", target=attempt,
            meta={"provider": "github", "transition": False},
        )
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    query = urlencode({
        "client_id": row.github_client_id, "redirect_uri": redirect_uri,
        "state": state, "scope": "read:user user:email",
        "code_challenge": challenge, "code_challenge_method": "S256",
    })
    return {"authorization_url": f"https://github.com/login/oauth/authorize?{query}",
            "state": state, "expires_in": settings.OIDC_ATTEMPT_TTL_SECONDS}
