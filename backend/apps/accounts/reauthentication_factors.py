"""Single-use second factors anchored to one consumed provider intent."""

import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from apps.accounts import audit_events
from apps.accounts.models_mfa import MFAChallenge, UserMFA
from apps.accounts.models_social import SocialIdentity


def second_factor(user):
    if UserMFA.objects.filter(user=user, enabled_at__isnull=False).exists():
        return "totp"
    if user.phone_e164 and user.phone_verified_at:
        from apps.integrations.sms import sms_configured
        if sms_configured():
            return "phone"
    if user.email and user.email_verified_at:
        return "email_code"
    return None


def _email_digest(code, token):
    return hmac.new(settings.SECRET_KEY.encode(), f"reauth-email:{token}:{code}".encode(), hashlib.sha256).hexdigest()


def start_factor(request, parent, subject):
    from apps.accounts.reauthentication_intents import _new, ProviderUnavailable
    from apps.accounts.services_phone import _issue
    from apps.accounts.models_phone import PhoneChallengePurpose

    method = second_factor(request.user)
    if method is None:
        raise PermissionDenied("No second verification factor is available.")
    with transaction.atomic():
        from apps.accounts.models import User
        from apps.accounts.reauthentication import versions
        request.user = User.objects.select_for_update().get(pk=request.user.pk)
        expected = versions(request.user)
        if (parent.auth_generation != expected["auth_generation"]
                or parent.credential_fingerprint != expected["credential_fingerprint"]
                or not SocialIdentity.objects.filter(user=request.user, provider=parent.context["provider"],
                                                     provider_sub=subject).exists()):
            raise AuthenticationFailed("Credentials changed. Start verification again.")
        # Re-evaluate the required factor while the credential owner is locked.
        method = second_factor(request.user)
        if method is None:
            raise PermissionDenied("No second verification factor is available.")
        raw, challenge = _new(request, "social_reauth_factor", provider=parent.context["provider"],
                              context={"parent_id": parent.pk, "subject": subject, "method": method,
                                       "email": request.user.email, "phone": request.user.phone_e164},
                              ttl=timedelta(minutes=10 if method == "email_code" else 5))
        if method == "email_code":
            code = f"{secrets.randbelow(1_000_000):06d}"
            challenge.context["code_digest"] = _email_digest(code, raw)
            challenge.save(update_fields=["context"])
    try:
        if method == "email_code":
            from apps.integrations.dispatch import dispatch_email
            log = dispatch_email(to_email=request.user.email, subject="Confirm your identity",
                                 text_body=f"Your identity verification code is {code}. It expires in 10 minutes.",
                                 stream="account", event="reauth_email_code", audience="staff", connection="platform",
                                 persist_body=False, sync=True)
            if log.status not in {"sent", "delivered"}:
                raise ProviderUnavailable()
        elif method == "phone":
            phone, sent = _issue(request.user, request.user.phone_e164, PhoneChallengePurpose.REAUTH)
            challenge.context["phone_challenge_id"] = phone.pk
            challenge.save(update_fields=["context"])
            if not sent:
                raise ProviderUnavailable()
    except Exception as exc:
        MFAChallenge.objects.filter(pk=challenge.pk).update(consumed_at=timezone.now())
        audit_events.record_auth_event(request.user, "auth.reauthentication_factor_delivery_failed", target=request.user)
        raise ProviderUnavailable() from exc
    return {"verified": False, "mfa_required": method == "totp", "factor_required": method,
            "factor_token": raw, "expires_in": 600 if method == "email_code" else 300}


def confirm_factor(request, *, token, code):
    from apps.accounts.reauthentication_intents import _checked
    from apps.accounts.reauthentication import stamp, WINDOW

    failed = False
    with transaction.atomic():
        row = _checked(request, token, "social_reauth_factor")
        context = row.context
        valid = row.attempts < 5 and SocialIdentity.objects.filter(
            user=request.user, provider=context["provider"], provider_sub=context["subject"]).exists()
        if valid and context["method"] == "totp":
            from apps.accounts.mfa_crypto import matching_step
            from apps.makerspaces.secrets import decrypt_value
            credential = UserMFA.objects.select_for_update().filter(user=request.user, enabled_at__isnull=False).first()
            step = (matching_step(decrypt_value(credential.secret), code, timezone.now().timestamp(), credential.last_step)
                    if credential else None)
            valid = step is not None
            if valid:
                credential.last_step = step
                credential.save(update_fields=["last_step"])
        elif valid and context["method"] == "phone":
            from apps.accounts.services_phone import _confirm
            from apps.accounts.models_phone import PhoneVerificationChallenge, PhoneChallengePurpose
            valid = bool(request.user.phone_verified_at and context["phone"] == request.user.phone_e164
                         and _confirm(PhoneVerificationChallenge.objects.filter(
                             pk=context.get("phone_challenge_id"), user=request.user, purpose=PhoneChallengePurpose.REAUTH),
                             code, context["phone"], on_failure=lambda _: None))
        elif valid and context["method"] == "email_code":
            valid = bool(request.user.email_verified_at and context["email"] == request.user.email
                         and hmac.compare_digest(context["code_digest"], _email_digest(code, token)))
        else:
            valid = False
        if not valid:
            row.attempts += 1
            if row.attempts >= 5:
                row.consumed_at = timezone.now()
            row.save(update_fields=["attempts", "consumed_at"])
            audit_events.record_auth_event(request.user, "auth.reauthentication_failed", target=request.user)
            failed = True
        else:
            row.consumed_at = timezone.now()
            row.save(update_fields=["consumed_at"])
            stamp(request)
    if failed:
        raise AuthenticationFailed("Invalid or expired verification code.")
    return {"verified": True, "mfa_required": False, "expires_in": int(WINDOW.total_seconds())}
