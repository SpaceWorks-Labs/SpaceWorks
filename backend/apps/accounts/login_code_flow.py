"""Emailed sign-in codes for the unusual-login check, on S0's ``login_codes`` primitives.

The code lives only as a digest inside its ``MFAChallenge.context``: ``purpose`` (``risk``),
``code_digest`` (HMAC bound to the purpose and the challenge id), ``sent_at`` and
``resends``. A code lasts ``LOGIN_CODE_TTL_SECONDS`` (10 minutes), shares the challenge's
``MFA_MAX_ATTEMPTS`` and may be resent at most twice; each resend replaces the code. The
mail is platform mail (``stream=account``, never persisted) sent after commit.
"""

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from apps.accounts import audit_events, login_codes
from apps.accounts.login_security_contract import LOGIN_CODE_INVALID, PURPOSE_RISK

logger = logging.getLogger(__name__)
MAX_RESENDS = 2


class LoginCodeRefused(ValidationError):
    def __init__(self, detail="This code can no longer be sent. Start signing in again."):
        super().__init__({"detail": detail, "code": LOGIN_CODE_INVALID})


def _subject(challenge):
    return f"mfa-challenge:{challenge.pk}"


def issue(challenge, *, resend=False):
    """Store a fresh code on ``challenge`` (caller saves nothing else) and mail it after
    commit. ``resend`` counts against the two allowed resends."""
    code = login_codes.new_code()
    now = timezone.now()
    context = dict(challenge.context or {})
    context.update(purpose=PURPOSE_RISK, code_digest=login_codes.digest(code, PURPOSE_RISK, _subject(challenge)),
                   sent_at=now.isoformat(), resends=int(context.get("resends", 0)) + (1 if resend else 0))
    challenge.context = context
    challenge.expires_at = login_codes.expires_at(now)
    challenge.save(update_fields=["context", "expires_at"])
    user_id = challenge.user_id
    transaction.on_commit(lambda: _send(user_id, code))
    audit_events.record_auth_event(challenge.user, "auth.login_code_sent", target=challenge.user,
                                   meta={"resend": resend})


def verify(challenge, code):
    """True when ``code`` is this challenge's current, unexpired code."""
    context = challenge.context or {}
    sent = parse_datetime(context.get("sent_at") or "")
    if context.get("purpose") != PURPOSE_RISK or sent is None:
        return False
    if login_codes.is_expired(login_codes.expires_at(sent)):
        return False
    return login_codes.verify(context.get("code_digest"), code, PURPOSE_RISK, _subject(challenge))


@transaction.atomic
def resend(raw, request):
    """Resend the code of one live risk challenge (POST ``auth/login-code/resend``)."""
    from apps.accounts.mfa_challenges import digest
    from apps.accounts.models_mfa import MFAChallenge
    challenge = (MFAChallenge.objects.select_for_update().select_related("user")
                 .filter(token_digest=digest(raw)).first())
    if (challenge is None or (challenge.context or {}).get("purpose") != PURPOSE_RISK
            or challenge.consumed_at is not None or challenge.expires_at <= timezone.now()
            or challenge.attempts >= settings.MFA_MAX_ATTEMPTS
            or int(challenge.context.get("resends", 0)) >= MAX_RESENDS):
        raise LoginCodeRefused()
    from apps.accounts.social_nonces import request_origin
    if challenge.context.get("origin", "") != request_origin(request):
        raise LoginCodeRefused()
    issue(challenge, resend=True)
    return {"sent": True, "expires_in": settings.LOGIN_CODE_TTL_SECONDS,
            "resends_left": MAX_RESENDS - int(challenge.context["resends"])}


def _send(user_id, code):
    from apps.accounts import security_alerts
    try:
        security_alerts.send_login_code(user_id, code)
    except Exception:
        logger.exception("login_code_send_failed")
