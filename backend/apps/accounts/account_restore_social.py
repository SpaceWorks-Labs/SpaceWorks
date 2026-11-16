"""Fresh, already-linked provider proof for accounts without email or phone."""

from django.utils.translation import gettext
import base64
import hashlib
import hmac
import json
import secrets
from datetime import timedelta
from types import SimpleNamespace
from urllib.parse import urlencode

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from apps.accounts.account_restore import identifier_fingerprint, restorable, restore_locked
from apps.accounts import audit_events
from apps.accounts.models import User, SocialIdentity
from apps.accounts.models_account_restore import AccountRestoreIntent
from apps.accounts.oidc_browser_attempts import _valid_redirect
from apps.accounts.reauthentication_intents import _provider, _digest, ProviderUnavailable
from apps.accounts.reauthentication_providers import freshness, provider_claims
from apps.accounts.social_jwt import SocialTokenError, SocialProviderUnavailable
from apps.accounts.oidc_browser_http import OidcTokenRejected, OidcProviderUnavailable
from apps.accounts.social_nonces import request_origin
from apps.makerspaces.cors import member_origin_is_registered
from apps.makerspaces.secrets import encrypt_value


def start_social(request, *, username, provider, redirect_uri="", delivery="web", client_platform="web", challenge=None):
    origin = request_origin(request)
    anchor = None
    if delivery == "web":
        if not member_origin_is_registered(origin) or not _valid_redirect(redirect_uri, origin):
            raise PermissionDenied(gettext("Use a registered member site to restore your account."))
    else:
        from apps.accounts.attestation import live_approved_challenge
        anchor = live_approved_challenge(challenge)
        if (anchor is None or provider not in {"apple", "google"}
                or client_platform != ("ios" if anchor.platform == "apple" else "android")):
            raise PermissionDenied(gettext("Use an approved application challenge to restore your account."))
        origin = ""
    if provider == "github":
        raise PermissionDenied(gettext("This provider cannot prove fresh authentication without a second factor."))
    try:
        _, endpoint, audience = _provider(provider)
    except OidcProviderUnavailable as exc:
        raise ProviderUnavailable() from exc
    if anchor:
        from apps.accounts.social_nonces import provider_settings, native_apple_audience, SocialAuthUnavailable
        try:
            configuration, audience = provider_settings(provider, client_platform)
        except SocialAuthUnavailable as exc:
            raise ProviderUnavailable() from exc
        if provider == "apple":
            audience = native_apple_audience(configuration, anchor)
    if not audience:
        raise ProviderUnavailable()
    # Unknown and ineligible usernames get the same provider redirect and intent shape.
    user = User.objects.filter(username=username).first()
    eligible = (restorable(user) and not user.email and not user.phone_e164
                and SocialIdentity.objects.filter(user=user, provider=provider).exists())
    raw, nonce, verifier = (secrets.token_urlsafe(48) for _ in range(3))
    intent = AccountRestoreIntent.objects.create(
        user=user if eligible else None, token_digest=_digest(raw), provider=provider,
        credential_fingerprint=identifier_fingerprint(user) if eligible else _digest(raw + nonce),
        nonce_digest=_digest(nonce), origin=origin, redirect_uri=redirect_uri,
        delivery=delivery, client_platform=client_platform, attestation_challenge=anchor,
        pending_secret=encrypt_value(verifier), expires_at=timezone.now() + timedelta(minutes=5),
    )
    audit_events.record_auth_event(None, "auth.account_restore_social_started", target=intent)
    query = {"client_id": audience, "redirect_uri": redirect_uri, "state": raw, "nonce": nonce,
             "scope": "openid email", "response_type": "id_token", "response_mode": "fragment"}
    if provider.startswith("oidc:"):
        query.update(prompt="login", max_age="0", response_type="code", response_mode="query",
                     code_challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode(),
                     code_challenge_method="S256")
    elif provider == "google":
        query["claims"] = json.dumps({"id_token": {"auth_time": {"essential": True}}})
    elif provider == "apple":
        query.pop("scope")
    return {"state": raw, "nonce": nonce, "expires_in": 300,
            "authorization_url": endpoint + ("&" if "?" in endpoint else "?") + urlencode(query)}


def complete_social(request, *, state, nonce, id_token="", code="", challenge="", attestation=None):
    failure = AuthenticationFailed(gettext("Invalid or expired restore proof."))
    with transaction.atomic():
        row = AccountRestoreIntent.objects.select_for_update().filter(token_digest=_digest(state)).first()
        valid = bool(row and not row.consumed_at and row.expires_at > timezone.now()
                     and (row.delivery == "device" or row.origin == request_origin(request))
                     and hmac.compare_digest(row.nonce_digest, _digest(nonce)))
        if row and not row.consumed_at:
            row.consumed_at = timezone.now()
            row.save(update_fields=["consumed_at"])
        audit_events.record_auth_event(None, "auth.account_restore_attempted", target=row)
    if not valid:
        raise failure
    intent = SimpleNamespace(context={"provider": row.provider, "redirect_uri": row.redirect_uri},
                             pending_secret=row.pending_secret)
    try:
        if row.delivery == "device":
            from apps.accounts.account_restore_social_device import device_claims
            claims = device_claims(row, nonce=nonce, id_token=id_token, challenge=challenge, attestation=attestation)
        else:
            claims = provider_claims(request, intent, nonce=nonce, id_token=id_token, code=code)
        if not freshness(row.provider, claims.get("auth_time")):
            raise SocialTokenError()
    except (OidcProviderUnavailable, SocialProviderUnavailable) as exc:
        raise ProviderUnavailable() from exc
    except (SocialTokenError, OidcTokenRejected) as exc:
        raise failure from exc
    with transaction.atomic():
        user = User.objects.select_for_update(no_key=True).filter(pk=row.user_id).first()
        try:
            still_fresh = freshness(row.provider, claims.get("auth_time"))
        except SocialTokenError:
            still_fresh = False
        if row.expires_at <= timezone.now() or not user or not still_fresh:
            raise failure
        if not SocialIdentity.objects.filter(
            user=user, provider=row.provider, provider_sub=claims["sub"],
        ).exists():
            raise failure
        return restore_locked(user, fingerprint=row.credential_fingerprint, social=True)
