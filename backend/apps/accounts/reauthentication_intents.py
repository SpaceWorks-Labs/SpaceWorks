"""Single-use social and email proofs bound to the existing browser session."""

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
from apps.makerspaces.secrets import encrypt_value, decrypt_value


class ProviderUnavailable(APIException):
    status_code = 503
    default_detail = "Identity provider or email delivery is unavailable. Try again later."
    default_code = "reauth_unavailable"


def _digest(raw):
    return hashlib.sha256(("reauth:v1:" + raw).encode()).hexdigest()


def _new(request, purpose, *, provider="", nonce="", verifier="", redirect_uri=""):
    sid, surface = binding(request)
    row = UserMFA.objects.filter(user=request.user).first()
    raw = secrets.token_urlsafe(48)
    challenge = MFAChallenge.objects.create(
        user=request.user, token_digest=_digest(raw), mfa_version=row.version if row else uuid.UUID(int=0),
        credential_fingerprint=versions(request.user)["credential_fingerprint"],
        auth_generation=versions(request.user)["auth_generation"],
        context={"purpose": purpose, "session_id": sid, "surface": surface,
                 "origin": request_origin(request), "provider": provider,
                 "nonce_digest": _digest(nonce), "redirect_uri": redirect_uri},
        pending_secret=encrypt_value(verifier) if verifier else "",
        expires_at=timezone.now() + timedelta(minutes=15 if purpose == "enrollment_email" else 5),
    )
    audit_events.record_auth_event(request.user, "auth.reauthentication_intent_created", target=request.user,
                                   meta={"purpose": purpose, "provider": provider, "surface": surface})
    return raw, challenge


def _consume(request, raw, purpose):
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
    row.consumed_at = now
    row.save(update_fields=["consumed_at"])
    audit_events.record_auth_event(request.user, "auth.reauthentication_intent_consumed", target=request.user,
                                   meta={"purpose": purpose, "surface": surface})
    return row


def _provider(key):
    # Built-in login protocols do not provide this OIDC freshness flow. Never
    # send generic prompt/response-mode parameters to Google or Apple.
    if not key.startswith("oidc:"):
        raise PermissionDenied("Use your password or authenticator to verify. If neither is available, "
                               "confirm the emailed enrollment link and enroll an authenticator.")
    from apps.accounts.login_methods import social_login_enabled
    if not social_login_enabled():
        raise ProviderUnavailable()
    from apps.accounts.models_oidc import provider_for_slug
    provider = provider_for_slug(key[5:])
    if provider is None:
        raise ProviderUnavailable()
    return provider, discover(provider)["authorization_endpoint"], provider.client_id


@transaction.atomic
def start_social(request, *, provider, redirect_uri):
    _trusted_origin(request)
    if not SocialIdentity.objects.filter(user=request.user, provider=provider).exists():
        raise PermissionDenied("Use an identity already linked to this account.")
    if not _valid_redirect(redirect_uri, request_origin(request)):
        raise PermissionDenied("Verification must return to this site's origin.")
    try:
        _, endpoint, audience = _provider(provider)
    except OidcProviderUnavailable as exc:
        raise ProviderUnavailable() from exc
    nonce, verifier = secrets.token_urlsafe(48), secrets.token_urlsafe(64)
    state, _ = _new(request, "social_reauth", provider=provider, nonce=nonce,
                    verifier=verifier, redirect_uri=redirect_uri)
    query = {"client_id": audience, "redirect_uri": redirect_uri, "scope": "openid email",
             "state": state, "nonce": nonce, "prompt": "login", "max_age": "0",
             "response_type": "code", "response_mode": "query"}
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
        provider, _, _ = _provider(key)
        from apps.accounts.social_oidc import verify_oidc_token
        id_token = exchange_code(provider, discover(provider), code=code,
                                 redirect_uri=intent.context["redirect_uri"],
                                 code_verifier=decrypt_value(intent.pending_secret))
        claims = verify_oidc_token(id_token, nonce=nonce, provider_row=provider)
        auth_time = claims.get("auth_time")
        now = timezone.now().timestamp()
        if (isinstance(auth_time, bool) or not isinstance(auth_time, (int, float))
                or not now - 60 <= auth_time <= now
                or not SocialIdentity.objects.filter(user=request.user, provider=key, provider_sub=claims["sub"]).exists()):
            raise SocialTokenError()
    except (OidcProviderUnavailable, SocialProviderUnavailable) as exc:
        raise ProviderUnavailable() from exc
    except (SocialTokenError, OidcTokenRejected) as exc:
        audit_events.record_auth_event(request.user, "auth.reauthentication_failed", target=request.user)
        raise AuthenticationFailed("The provider could not prove fresh authentication. Enroll an authenticator using the email confirmation fallback.") from exc
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
        stamp(request, field="social_verified_at")
        credential = UserMFA.objects.select_for_update().filter(user=request.user).first()
        if credential and credential.enabled_at:
            from apps.accounts.reauthentication import verify
            # MFA must follow the provider's freshly verified first factor.
            if not totp:
                return {"verified": False, "mfa_required": True, "expires_in": 300}
            return verify(request, code=totp)
        stamp(request)
    return {"verified": True, "mfa_required": False, "expires_in": 600}


def _trusted_origin(request):
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
