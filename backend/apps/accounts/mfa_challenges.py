"""Opaque, expiring first-factor proofs; no JWT exists until the second factor succeeds."""

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts import audit_events
from apps.accounts.mfa_crypto import new_secret, provisioning_uri
from apps.accounts.mfa_policy import assert_available, stamp
from apps.accounts.models import User
from apps.accounts.models_mfa import MFAChallenge, UserMFA
from apps.accounts.password_reset_crypto import credential_fingerprint
from apps.accounts.services_mfa import active, consume_code, enable
from apps.accounts.tokens import current_auth_generation
from apps.accounts.services_device_grants import DeviceSuperadminNotSupported, audit_grant_refusal
from apps.accounts.session_issuance import lock_session_user
from apps.makerspaces.secrets import decrypt_value, encrypt_value


SETTINGS_ENROLL = "settings_enroll"


def digest(raw):
    return hashlib.sha256(str(raw).encode()).hexdigest()


@transaction.atomic
def start(user, *, context):
    assert_available()
    user = lock_session_user(user)
    active(user)
    from apps.accounts.surface_policy import assert_surface, token_kind
    assert_surface(user, context.get("surface"), request=None)
    context = {**context, "kind": token_kind(user), "credential_generation": user.credential_generation}
    row, _ = UserMFA.objects.get_or_create(user=user)
    raw = secrets.token_urlsafe(32)
    challenge = MFAChallenge.objects.create(
        user=user, token_digest=digest(raw), mfa_version=row.version,
        credential_fingerprint=credential_fingerprint(user, user.email),
        auth_generation=current_auth_generation(), context=context,
        expires_at=timezone.now() + timedelta(seconds=settings.MFA_CHALLENGE_TTL_SECONDS),
    )
    audit_events.record_auth_event(user, "auth.mfa_challenge_created", target=user)
    return {"mfa_required": True, "enrollment_required": not bool(row.enabled_at),
            "challenge": raw, "expires_in": settings.MFA_CHALLENGE_TTL_SECONDS}


def _settings_device(challenge):
    device = challenge.context.get("device") or {}
    return device if device.get("purpose") == SETTINGS_ENROLL else None


def _same_settings_device(challenge, request):
    """A settings enrollment started on a device never finishes on another session.

    Starting enrollment invalidates the caller's tokens (the new MFA row changes the
    version they were minted against), so, as on the web, the challenge itself is the
    credential for enroll/confirm. A presented session must still be that same grant;
    issue_session refuses browser headers and re-issues only on the recorded grant.
    """
    device = _settings_device(challenge)
    if device is None:
        return True
    grant = getattr(request, "device_grant", None)
    if grant is not None and str(grant.pk) != device["grant_id"]:
        return False
    return getattr(request, "auth", None) is None or grant is not None


def _kept_grant(challenge, user):
    from apps.accounts.models_devices import DeviceGrant
    device = _settings_device(challenge)
    if device is None:
        return None
    grant = DeviceGrant.objects.filter(pk=device["grant_id"], user=user,
                                       status=DeviceGrant.Status.ACTIVE).first()
    if grant is None:
        raise AuthenticationFailed("Device authorization is no longer active.")
    return grant


def _locked(raw, request):
    candidate = MFAChallenge.objects.filter(token_digest=digest(raw)).values("pk", "user_id").first()
    if candidate is None:
        raise AuthenticationFailed("Invalid or expired MFA challenge.")
    # Use the same User -> credential -> challenge lock order as management/recovery.
    user = User.objects.select_for_update().get(pk=candidate["user_id"])
    row = UserMFA.objects.select_for_update().get(user=user)
    challenge = MFAChallenge.objects.select_for_update().filter(pk=candidate["pk"]).first()
    if challenge is None:
        raise AuthenticationFailed("Invalid or expired MFA challenge.")
    active(user)
    from apps.accounts.surface_policy import assert_surface, validate_account_token
    validate_account_token(user, challenge.context)
    assert_surface(user, challenge.context.get("surface"), request=request)
    from apps.accounts.social_nonces import request_origin
    origin = request_origin(request)
    if challenge.context.get("surface") == "control":
        if request.path != "/mfa/control/" or request.user.pk != user.pk:
            raise AuthenticationFailed("Invalid or expired MFA challenge.")
        from urllib.parse import urlsplit
        origin = urlsplit(request.build_absolute_uri("/")).geturl().rstrip("/")
    valid = (challenge.consumed_at is None and challenge.expires_at > timezone.now()
             and challenge.attempts < settings.MFA_MAX_ATTEMPTS
             and challenge.auth_generation == current_auth_generation()
             and challenge.context.get("credential_generation") == user.credential_generation
             and challenge.credential_fingerprint == credential_fingerprint(user, user.email)
             and challenge.mfa_version == row.version
             and challenge.context.get("origin", "") == origin
             and _same_settings_device(challenge, request))
    if not valid:
        raise AuthenticationFailed("Invalid or expired MFA challenge.")
    return challenge, user, row


@transaction.atomic
def enroll(raw, request):
    assert_available()
    challenge, user, row = _locked(raw, request)
    if row.enabled_at:
        raise AuthenticationFailed("MFA is already enrolled.")
    if not challenge.pending_secret:
        challenge.pending_secret = encrypt_value(new_secret())
        challenge.save(update_fields=["pending_secret"])
        audit_events.record_auth_event(user, "auth.mfa_enrollment_started", target=user)
    secret = decrypt_value(challenge.pending_secret)
    uri = provisioning_uri(secret, user.username)
    import base64
    import io
    import segno
    output = io.BytesIO()
    segno.make(uri, micro=False).save(output, kind="png", scale=5)
    return {"secret": secret, "provisioning_uri": uri,
            "qr_data_url": "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()}


def finish(raw, code, request, *, enrolling=False):
    try:
        return _finish(raw, code, request, enrolling=enrolling)
    except DeviceSuperadminNotSupported as exc:
        # _finish's transaction has rolled back, including any enrollment changes.
        audit_grant_refusal(exc)
        raise


def _finish(raw, code, request, *, enrolling):
    assert_available()
    refusal = False
    result = None
    with transaction.atomic():
        challenge, user, row = _locked(raw, request)
        codes = None
        if enrolling and not row.enabled_at and challenge.pending_secret:
            # Settings enrollment on a device keeps that grant and re-issues its tokens.
            keep = _kept_grant(challenge, user)
            codes = enable(user, row, decrypt_value(challenge.pending_secret), code, keep_grant=keep)
            valid = codes is not None
        elif _settings_device(challenge):
            # A settings challenge only enrolls; it is never a second sign-in on its grant.
            valid = False
        else:
            valid = bool(not enrolling and row.enabled_at and consume_code(row, code))
        if not valid:
            challenge.attempts += 1
            challenge.save(update_fields=["attempts"])
            audit_events.record_auth_event(user, "auth.mfa_failed", target=user)
            refusal = True
        else:
            stamp(user, row)
            # Context is server-owned; callers cannot widen the login's surface or device.
            from apps.accounts.mfa_sessions import issue_session
            result = issue_session(user, challenge.context, request)
            if codes is not None:
                result["recovery_codes"] = codes
            challenge.consumed_at = timezone.now()
            challenge.pending_secret = ""
            challenge.save(update_fields=["consumed_at", "pending_secret"])
            audit_events.record_auth_event(user, "auth.mfa_verified", target=user)
    if refusal:
        raise AuthenticationFailed("Invalid or expired MFA challenge.")
    return result
