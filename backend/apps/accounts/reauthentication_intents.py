"""Single-use social and email proofs bound to a browser session or device family."""

import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import timedelta
from urllib.parse import urlencode

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied, APIException

from apps.accounts import audit_events
from apps.accounts.models_mfa import MFAChallenge, UserMFA
from apps.accounts.models_social import SocialIdentity
from apps.accounts.oidc_browser_attempts import _valid_redirect
from apps.accounts.oidc_browser_http import discover, exchange_code, OidcProviderUnavailable, OidcTokenRejected
from apps.accounts.reauthentication import binding, stamp, versions
from apps.accounts.social_jwt import SocialTokenError, SocialProviderUnavailable
from apps.accounts.social_nonces import request_origin
from apps.makerspaces.secrets import encrypt_value


class ProviderUnavailable(APIException):
    status_code = 503
    default_detail = "Identity provider or email delivery is unavailable. Try again later."
    default_code = "reauth_unavailable"


def _digest(raw):
    return hashlib.sha256(("reauth:v1:" + raw).encode()).hexdigest()


def _new(request, purpose, *, provider="", nonce="", verifier="", redirect_uri="", context=None, ttl=None):
    sid, surface = binding(request)
    row = UserMFA.objects.filter(user=request.user).first()
    raw = secrets.token_urlsafe(48)
    challenge = MFAChallenge.objects.create(
        user=request.user, token_digest=_digest(raw), mfa_version=row.version if row else uuid.UUID(int=0),
        credential_fingerprint=versions(request.user)["credential_fingerprint"],
        auth_generation=versions(request.user)["auth_generation"],
        context={"purpose": purpose, "session_id": sid, "surface": surface,
                 "origin": request_origin(request), "provider": provider,
                 "nonce_digest": _digest(nonce), "redirect_uri": redirect_uri, **(context or {})},
        pending_secret=encrypt_value(verifier) if verifier else "",
        expires_at=timezone.now() + (ttl or timedelta(minutes=15 if purpose == "enrollment_email" else 5)),
    )
    audit_events.record_auth_event(request.user, "auth.reauthentication_intent_created", target=request.user,
                                   meta={"purpose": purpose, "provider": provider, "surface": surface})
    return raw, challenge


def _checked(request, raw, purpose):
    from apps.accounts.models import User
    request.user = User.objects.select_for_update().get(pk=request.user.pk)
    sid, surface = binding(request)
    row = MFAChallenge.objects.select_for_update().filter(user=request.user, token_digest=_digest(raw)).first()
    now = timezone.now()
    valid = (row and row.consumed_at is None and row.expires_at > now
             and row.context.get("purpose") == purpose and row.context.get("session_id") == sid
             and row.context.get("surface") == surface and row.context.get("origin") == request_origin(request)
             and row.auth_generation == versions(request.user)["auth_generation"]
             and row.credential_fingerprint == versions(request.user)["credential_fingerprint"]
             and str(row.mfa_version) == (versions(request.user)["mfa_version"] or str(uuid.UUID(int=0))))
    if not valid:
        raise AuthenticationFailed("Invalid or expired verification intent.")
    return row


def _consume(request, raw, purpose):
    row = _checked(request, raw, purpose)
    now = timezone.now()
    row.consumed_at = now
    row.save(update_fields=["consumed_at"])
    audit_events.record_auth_event(request.user, "auth.reauthentication_intent_consumed", target=request.user,
                                   meta={"purpose": purpose, "surface": row.context["surface"]})
    return row


def _provider(key):
    from apps.accounts.login_methods import social_login_enabled
    if not social_login_enabled():
        raise ProviderUnavailable()
    if key in {"google", "apple", "github"}:
        from apps.accounts.models_social import PlatformSocialAuthSettings
        from apps.accounts.social_lockout import provider_configured
        row = PlatformSocialAuthSettings.objects.filter(pk=1).first()
        if not provider_configured(row, key):
            raise ProviderUnavailable()
        endpoint = {"google": "https://accounts.google.com/o/oauth2/v2/auth",
                    "apple": "https://appleid.apple.com/auth/authorize",
                    "github": "https://github.com/login/oauth/authorize"}[key]
        client = row.github_client_id if key == "github" else row.client_id(key, "web")
        return row, endpoint, client
    if not key.startswith("oidc:"):
        raise PermissionDenied("Use an identity already linked to this account.")
    from apps.accounts.models_oidc import provider_for_slug
    provider = provider_for_slug(key[5:])
    if provider is None:
        raise ProviderUnavailable()
    return provider, discover(provider)["authorization_endpoint"], provider.client_id


@transaction.atomic
def start_social(request, *, provider, redirect_uri=""):
    _trusted_origin(request)
    if not SocialIdentity.objects.filter(user=request.user, provider=provider).exists():
        raise PermissionDenied("Use an identity already linked to this account.")
    native = bool(getattr(request, "auth", None) and request.auth.get("device_grant_id"))
    if not native and not _valid_redirect(redirect_uri, request_origin(request)):
        raise PermissionDenied("Verification must return to this site's origin.")
    try:
        configuration, endpoint, audience = _provider(provider)
    except OidcProviderUnavailable as exc:
        raise ProviderUnavailable() from exc
    if native and provider in {"google", "apple"}:
        from apps.accounts.models_devices import DeviceGrant
        grant = DeviceGrant.objects.get(pk=request.auth["device_grant_id"], user=request.user)
        platform = "ios" if grant.platform == "apple" else "android"
        audience = configuration.client_id(provider, platform)
        if provider == "apple":
            audience = grant.app_id if grant.app_id in configuration.apple_native_app_ids else ""
        if not audience:
            raise ProviderUnavailable()
    if provider == "github":
        from apps.accounts.reauthentication_factors import second_factor
        if second_factor(request.user) is None:
            raise PermissionDenied("No second verification factor is available.")
    nonce, verifier = secrets.token_urlsafe(48), secrets.token_urlsafe(64)
    state, _ = _new(request, "social_reauth", provider=provider, nonce=nonce,
                    verifier=verifier, redirect_uri=redirect_uri)
    query = {"client_id": audience, "redirect_uri": redirect_uri, "scope": "openid email",
             "state": state, "nonce": nonce,
             "response_type": "code", "response_mode": "query"}
    if provider.startswith("oidc:"):
        query.update(prompt="login", max_age="0")
    elif provider == "google":
        import json
        query.update(claims=json.dumps({"id_token": {"auth_time": {"essential": True}}}))
        query["response_type"] = "id_token"
        query["response_mode"] = "fragment"
    elif provider == "apple":
        query.update(response_type="id_token", response_mode="fragment")
        # Existing identities need no name/email consent. Apple's consent scopes
        # force form_post, whereas this token-only callback uses a fragment.
        query.pop("scope")
    elif provider == "github":
        query["scope"] = "read:user user:email"
        query.pop("nonce")
    if provider not in {"google", "apple"}:
        query.update(code_challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode(),
                     code_challenge_method="S256")
    return {"authorization_url": endpoint + ("&" if "?" in endpoint else "?") + urlencode(query),
            "state": state, "nonce": nonce, "expires_in": 300}


def complete_social(request, *, state, nonce, id_token="", code="", totp=""):
    # Commit intent consumption even when a provider refuses freshness. Replaying
    # a failed response must never turn it into a new authentication attempt.
    with transaction.atomic():
        intent = _consume(request, state, "social_reauth")
    try:
        if not hmac.compare_digest(intent.context["nonce_digest"], _digest(nonce)):
            raise SocialTokenError()
        key = intent.context["provider"]
        from apps.accounts.reauthentication_providers import provider_claims, freshness
        claims = provider_claims(request, intent, nonce=nonce, id_token=id_token, code=code)
        fresh = freshness(key, claims.get("auth_time"))
        if not SocialIdentity.objects.filter(user=request.user, provider=key, provider_sub=claims["sub"]).exists():
            raise SocialTokenError()
    except (OidcProviderUnavailable, SocialProviderUnavailable) as exc:
        raise ProviderUnavailable() from exc
    except (SocialTokenError, OidcTokenRejected) as exc:
        audit_events.record_auth_event(request.user, "auth.reauthentication_failed", target=request.user)
        raise AuthenticationFailed("The provider could not verify this linked identity. Start verification again.") from exc
    with transaction.atomic():
        from apps.accounts.models import User
        locked = User.objects.select_for_update().get(pk=request.user.pk)
        request.user = locked
        expected = versions(locked)
        if (intent.auth_generation != expected["auth_generation"]
                or intent.credential_fingerprint != expected["credential_fingerprint"]
                or str(intent.mfa_version) != (expected["mfa_version"] or str(uuid.UUID(int=0)))):
            raise AuthenticationFailed("Credentials changed. Start verification again.")
        if not SocialIdentity.objects.filter(user=locked, provider=key, provider_sub=claims["sub"]).exists():
            raise AuthenticationFailed("The linked identity was revoked. Start verification again.")
        credential = UserMFA.objects.select_for_update().filter(user=request.user).first()
        needs_factor = not fresh or bool(credential and credential.enabled_at)
        if not needs_factor:
            stamp(request, field="social_verified_at")
            stamp(request)
    if needs_factor:
        from apps.accounts.reauthentication_factors import start_factor, confirm_factor
        factor = start_factor(request, intent, claims["sub"])
        if totp and factor["factor_required"] == "totp":
            return confirm_factor(request, token=factor["factor_token"], code=totp)
        return factor
    return {"verified": True, "mfa_required": False, "expires_in": 600}


def _trusted_origin(request):
    if getattr(request, "auth", None) and request.auth.get("device_grant_id"):
        binding(request)
        return
    from apps.makerspaces.cors import member_origin_is_registered, staff_origin_is_registered
    origin = request_origin(request)
    if not origin or not (member_origin_is_registered(origin) or staff_origin_is_registered(origin)):
        raise PermissionDenied("Use a registered site origin to verify your identity.")


def start_email(request):
    _trusted_origin(request)
    if request.user.has_usable_password() or request.user.email_verified_at is None or not request.user.email:
        raise PermissionDenied("A verified email address on a passwordless account is required.")
    with transaction.atomic():
        raw, intent = _new(request, "enrollment_email")
    origin = request_origin(request)
    if not origin:
        raise PermissionDenied("Open this page in the browser to request a confirmation link.")
    from apps.integrations.dispatch import dispatch_email
    try:
        log = dispatch_email(to_email=request.user.email, subject="Confirm authenticator enrollment",
                             text_body="Confirm enrollment in the same browser session within 15 minutes: "
                             + origin + "/reauth/confirm#token=" + raw,
                             stream="account", event="reauth_enrollment", audience="staff", connection="platform",
                             persist_body=False, sync=True)
        if log.status not in {"sent", "delivered"}:
            raise ProviderUnavailable()
    except Exception as exc:
        MFAChallenge.objects.filter(pk=intent.pk, consumed_at__isnull=True).update(consumed_at=timezone.now())
        audit_events.record_auth_event(request.user, "auth.reauthentication_email_failed", target=request.user)
        raise ProviderUnavailable() from exc
    return {"sent": True}


@transaction.atomic
def confirm_email(request, token):
    _consume(request, token, "enrollment_email")
    stamp(request, field="enrollment_confirmed_at")
    return {"confirmed": True}
