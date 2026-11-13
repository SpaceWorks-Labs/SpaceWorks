"""Session-bound recent authentication, independent of separable domain apps."""

from django.utils.translation import gettext
from datetime import timedelta
import hashlib
import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from apps.accounts import audit_events, mfa_policy
from apps.accounts.models import User
from apps.accounts.models_mfa import UserMFA
from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.accounts.password_reset_crypto import credential_fingerprint
from apps.accounts.services_mfa import active
from apps.accounts.staff_identity import context_label, is_person, is_platform
from apps.accounts.tokens import current_auth_generation

WINDOW = timedelta(minutes=10)


class RecentAuthenticationRequired(PermissionDenied):
    def __init__(self):
        super().__init__({"detail": "Confirm your identity to continue. Verification lasts ten minutes.",
                          "code": "recent_reauth_required"})


def binding(request):
    user = request.user
    active(user)
    if user.deletion_requested_at is not None:
        raise AuthenticationFailed(gettext("Account is not available."))
    token = getattr(request, "auth", None)
    if token is not None:
        from apps.accounts.surface_policy import assert_surface, validate_account_token
        validate_account_token(user, token)
        from apps.accounts.session_issuance import validate_session_generation
        validate_session_generation(user, token)
        assert_surface(user, token.get("surface"), request=request)
        if token.get("device_grant_id"):
            from apps.accounts.models_devices import DeviceRefreshFamily
            from apps.accounts.native_app_identity import registration_is_eligible
            try:
                family = DeviceRefreshFamily.objects.select_related("grant__registration").filter(
                    pk=token.get("device_family_id"), grant_id=token["device_grant_id"], user=user,
                    grant__user=user, revoked_at__isnull=True,
                    grant__status="active", grant__revoked_at__isnull=True).first()
            except (ValidationError, ValueError, TypeError) as exc:
                raise PermissionDenied(gettext("A current device session is required.")) from exc
            staff_grant = family is not None and family.grant.authority in ("staff", "event")
            if (family is None or not registration_is_eligible(family.grant.registration)
                    or token.get("surface") != "member" or not is_person(user)
                    or family.grant.credential_generation != user.credential_generation
                    or staff_grant and (
                        token.get("mfa_source") != "verified"
                        or family.grant.authority == "staff"
                        and family.grant.registration.makerspace_id not in (None, family.grant.staff_makerspace_id))):
                raise PermissionDenied(gettext("A current device session is required."))
            return "device:" + str(family.pk), token["surface"]
        if token.get("surface") not in {"member", "platform"}:
            raise PermissionDenied(gettext("Use a browser session to verify your identity."))
        from apps.accounts.web_sessions import validate_session
        row = validate_session(user, token)
        if row is None:
            raise PermissionDenied(gettext("Sign in again before verifying your identity."))
        return row.jti, token["surface"]
    if not getattr(request, "session", None) or not request.session.session_key:
        raise PermissionDenied(gettext("A current browser session is required."))
    from apps.accounts.control_mfa import session_verified
    if not is_platform(user) or not user.is_superuser or not session_verified(request):
        raise PermissionDenied(gettext("Complete the control-panel MFA gate first."))
    return "control:" + request.session.session_key, "control"


def versions(user):
    row = mfa_policy.credential(user)
    # Linked identities are credentials too. Include row identity so an unlink/
    # relink cannot resurrect a proof made before the credential was revoked.
    identities = list(user.social_identities.order_by("pk").values_list("pk", "provider", "provider_sub"))
    identity = (str(user.pk), context_label(user), user.credential_generation)
    phone = [user.phone_e164, str(user.phone_verified_at or "")]
    fingerprint = hashlib.sha256((credential_fingerprint(user, user.email) + "\0"
                                  + json.dumps([identity, identities, phone, str(user.account_restored_at or "")])).encode()).hexdigest()
    return {"auth_generation": current_auth_generation(),
            "credential_fingerprint": fingerprint,
            "mfa_version": str(row.version) if row else ""}


def current(request, *, lock=False):
    sid, surface = binding(request)
    rows = ReauthenticationSession.objects
    if lock:
        rows = rows.select_for_update()
    row = rows.filter(session_id=sid, user=request.user, surface=surface, **versions(request.user)).first()
    return row


def require_recent_reauth(request):
    row = current(request)
    now = timezone.now()
    if row is None or row.auth_time is None or not now - WINDOW <= row.auth_time <= now:
        raise RecentAuthenticationRequired()
    return row


def stamp(request, *, field="auth_time"):
    sid, surface = binding(request)
    values = versions(request.user)
    row, _ = ReauthenticationSession.objects.get_or_create(
        session_id=sid, defaults={"user": request.user, "surface": surface, **values})
    if row.user_id != request.user.pk:
        raise PermissionDenied()
    if row.surface != surface or any(getattr(row, key) != value for key, value in values.items()):
        row.auth_time = row.social_verified_at = row.enrollment_confirmed_at = None
    row.surface = surface
    for key, value in values.items():
        setattr(row, key, value)
    setattr(row, field, timezone.now())
    if field == "auth_time":
        credential = mfa_policy.credential(request.user)
        if credential and credential.enabled_at:
            # A completed MFA step consumes its pending provider first factor.
            row.social_verified_at = None
    row.save()
    audit_events.record_auth_event(request.user, "auth.reauthenticated" if field == "auth_time"
                                   else "auth.reauthentication_factor_verified", target=request.user,
                                   meta={"surface": surface, "factor": field})
    return row


def verify(request, *, password="", code=""):
    refusal = False
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=request.user.pk)
        active(user)
        request.user = user
        binding(request)
        row = UserMFA.objects.select_for_update().filter(user=user).first()
        mfa = bool(row and row.enabled_at)
        if not mfa and mfa_policy.has_passkey(user):
            from apps.accounts.passkeys.policy import passkeys_usable
            if passkeys_usable(user):
                # A second factor exists: a password alone is not a step-up (reauth/passkey).
                from apps.accounts.login_security_contract import PASSKEY_REQUIRED
                raise PermissionDenied({"detail": gettext("Confirm with your passkey."), "code": PASSKEY_REQUIRED})
        proof = current(request)
        social = bool(mfa and proof and proof.social_verified_at and
                      timezone.now() - timedelta(minutes=5) <= proof.social_verified_at <= timezone.now())
        valid = (social or user.check_password(password)) if user.has_usable_password() else mfa
        if valid and mfa:
            # Step-up requires an actual TOTP, never a recovery code. The same
            # locked counter as ordinary MFA makes a replay fail across both paths.
            from apps.accounts.mfa_crypto import matching_step
            from apps.makerspaces.secrets import decrypt_value
            step = matching_step(decrypt_value(row.secret), code, timezone.now().timestamp(), row.last_step)
            valid = step is not None
            if valid:
                row.last_step = step
                row.save(update_fields=["last_step"])
        if not valid:
            audit_events.record_auth_event(user, "auth.reauthentication_failed", target=user)
            refusal = True
        else:
            stamp(request)
    if refusal:
        raise AuthenticationFailed(gettext("Identity verification failed."))
    return {"verified": True, "expires_in": int(WINDOW.total_seconds())}


def require_enrollment_proof(request):
    row = current(request)
    now = timezone.now()
    valid_social = row and row.social_verified_at and now - timedelta(minutes=5) <= row.social_verified_at <= now
    valid_email = row and row.enrollment_confirmed_at and now - timedelta(minutes=15) <= row.enrollment_confirmed_at <= now
    # A phone-only member has no email link to confirm from a native app, so a fresh phone
    # OTP proof on the same device session stands in for it (device sessions only).
    valid_phone = False
    if row and row.session_id.startswith("device:") and row.auth_time and now - timedelta(minutes=5) <= row.auth_time <= now:
        from apps.accounts.reauthentication_phone import available
        valid_phone = available(request.user)
    if not (valid_social or valid_email or valid_phone):
        raise PermissionDenied(gettext("Verify a fresh linked social identity or confirm the session-bound email link before enrolling."),
                               code="reauth_enrollment_required")
