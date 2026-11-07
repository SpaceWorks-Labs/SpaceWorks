"""Phone-only recent authentication with committed OTP attempt accounting."""

from django.utils.translation import gettext
import logging

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts import audit_events
from apps.accounts.models_phone import PhoneChallengePurpose, PhoneVerificationChallenge
from apps.accounts.reauthentication import stamp
from apps.accounts.reauthentication_intents import _new, _checked, _trusted_origin
from apps.accounts.services_phone import _issue, _confirm, ChallengeCooldown
from apps.accounts.staff_identity import is_person

logger = logging.getLogger(__name__)


def available(user):
    from apps.accounts.models_mfa import UserMFA
    from apps.integrations.sms import sms_configured
    return bool(is_person(user) and user.phone_e164 and user.phone_verified_at and not user.has_usable_password()
                and not user.social_identities.exists()
                and not UserMFA.objects.filter(user=user, enabled_at__isnull=False).exists()
                and sms_configured())


def start(request):
    _trusted_origin(request)
    with transaction.atomic():
        raw, intent = _new(request, "phone_reauth", context={"phone": request.user.phone_e164})
    if available(request.user):
        try:
            challenge, _ = _issue(request.user, request.user.phone_e164, PhoneChallengePurpose.REAUTH)
            intent.context["phone_challenge_id"] = challenge.pk
            intent.save(update_fields=["context"])
        except ChallengeCooldown:
            pass
        except Exception:
            logger.warning("reauthentication_phone_delivery_failed", extra={"user_id": request.user.pk})
            audit_events.record_auth_event(request.user, "auth.reauthentication_factor_delivery_failed", target=request.user)
    # Availability, cooldown and delivery all have the same authenticated response.
    return {"sent": True, "token": raw}


def confirm(request, *, token, code):
    failed = False
    with transaction.atomic():
        intent = _checked(request, token, "phone_reauth")
        phone = intent.context["phone"]
        valid = bool(available(request.user) and phone == request.user.phone_e164
                     and _confirm(PhoneVerificationChallenge.objects.filter(
                         pk=intent.context.get("phone_challenge_id"), user=request.user,
                         purpose=PhoneChallengePurpose.REAUTH), code, phone,
                         on_failure=lambda _: None))
        if not valid:
            intent.attempts += 1
            if intent.attempts >= 5:
                intent.consumed_at = timezone.now()
            intent.save(update_fields=["attempts", "consumed_at"])
            audit_events.record_auth_event(request.user, "auth.reauthentication_failed", target=request.user)
            failed = True
        else:
            intent.consumed_at = timezone.now()
            intent.save(update_fields=["consumed_at"])
            stamp(request)
    if failed:
        raise AuthenticationFailed(gettext("Invalid or expired verification code."))
    return {"verified": True, "expires_in": 600}
