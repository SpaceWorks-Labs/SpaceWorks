"""Start, prove, resend and cancel an account merge (decision #65, Q16; U-C).

Nothing merges on email alone. The survivor (the signed-in person) proves the source by:

- ``credentials``: the source's password AND its authenticator (TOTP or a recovery code);
  a source with no factor cannot use this method (``factor_enrolment_required``, said
  only after the password matched);
- ``email_codes``: two fresh 6-digit codes, one to the survivor's email and one to the
  source's current or held email; both are required, even when both go to the same mailbox.

Codes are never stored: only ``login_codes.digest(code, purpose, intent)``. Each intent
lives 10 minutes, allows ``login_codes.MAX_ATTEMPTS`` failed proofs in total and its codes
work once. ``start`` answers identically for an unknown identifier (the intent then has no
source, so every proof fails), and the survivor's own code is sent either way.
Refusals commit their counters and audit before raising.
"""

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.accounts import login_codes
from apps.accounts.account_merge_eligibility import (
    FACTOR_ENROLMENT_REQUIRED, PROOF_EXPIRED, PROOF_FAILED, MergeRefused, identifier_digest,
    require_survivor, resolve_source, source_email,
)
from apps.audit import services as audit
from apps.accounts.models_account_merge import AccountMergeIntent as Intent

logger = logging.getLogger(__name__)
TTL = timedelta(minutes=10)
MAX_RESENDS = 3
SURVIVOR, SOURCE = "account_merge:survivor", "account_merge:source"
OPEN = (Intent.State.STARTED, Intent.State.PROVED)


def start(survivor, identifier, method):
    require_survivor(survivor)
    from apps.accounts.account_merge_eligibility import MERGE_NOT_ALLOWED
    if method == Intent.Method.EMAIL_CODES and not (survivor.email or "").strip():
        raise MergeRefused(MERGE_NOT_ALLOWED, "Add an email address to this account first.")
    now = timezone.now()
    with transaction.atomic():
        for open_intent in Intent.objects.select_for_update().filter(survivor=survivor, state__in=OPEN):
            _close(open_intent, Intent.State.CANCELLED, now)
        intent = Intent.objects.create(
            survivor=survivor, source=resolve_source(identifier, survivor), method=method,
            identifier_digest=identifier_digest(identifier), expires_at=now + TTL)
        codes = _issue(intent, now) if method == Intent.Method.EMAIL_CODES else None
        audit.record(survivor, "account.merge_started", target=survivor, meta={"method": method})
    if codes:
        _send(intent, codes)
    return intent


def _issue(intent, now):
    codes = {SURVIVOR: login_codes.new_code(), SOURCE: login_codes.new_code()}
    intent.survivor_code_digest = login_codes.digest(codes[SURVIVOR], SURVIVOR, intent.pk)
    intent.source_code_digest = login_codes.digest(codes[SOURCE], SOURCE, intent.pk)
    intent.survivor_code_verified_at = intent.source_code_verified_at = None
    intent.sent_at, intent.expires_at = now, now + TTL
    intent.save(update_fields=["survivor_code_digest", "source_code_digest", "survivor_code_verified_at",
                               "source_code_verified_at", "sent_at", "expires_at"])
    return codes


def _send(intent, codes):
    """Two separate messages, even to one mailbox (Q16). Delivery failures are only logged,
    so the answer never reveals whether the identifier named an account."""
    from apps.accounts.account_merge_mail import send_code

    send_code(intent.survivor.email, codes[SURVIVOR], side="survivor")
    if intent.source is not None and (address := source_email(intent.source)):
        send_code(address, codes[SOURCE], side="source")


def locked_intent(survivor, intent_id):
    from django.core.exceptions import ValidationError
    from rest_framework.exceptions import NotFound

    try:
        # No select_related: ``source`` is nullable and FOR UPDATE refuses an outer join.
        intent = Intent.objects.select_for_update().get(pk=intent_id, survivor=survivor)
    except (Intent.DoesNotExist, ValidationError, ValueError):
        raise NotFound("Merge not found.") from None
    return intent


def _live(intent, now, states=(Intent.State.STARTED,)):
    if intent.state in OPEN and (now >= intent.expires_at or login_codes.attempts_exhausted(intent.attempts)):
        _close(intent, Intent.State.EXPIRED, now)
    return intent.state in states


def _close(intent, state, now):
    intent.state = state
    intent.survivor_code_digest = intent.source_code_digest = ""
    if state == Intent.State.CANCELLED:
        intent.cancelled_at = now
    intent.save(update_fields=["state", "survivor_code_digest", "source_code_digest", "cancelled_at"])


def prove(survivor, intent_id, data):
    now, failure = timezone.now(), None
    with transaction.atomic():
        intent = locked_intent(survivor, intent_id)
        if intent.state == Intent.State.PROVED and now < intent.expires_at:
            return intent
        if not _live(intent, now):
            failure = (PROOF_EXPIRED, "This link request expired. Start again.")
        else:
            failure = _check(intent, data, now)
            if failure is None:
                intent.state, intent.proved_at, intent.expires_at = Intent.State.PROVED, now, now + TTL
                intent.survivor_code_digest = intent.source_code_digest = ""
                intent.save(update_fields=["state", "proved_at", "expires_at", "survivor_code_digest",
                                           "source_code_digest", "survivor_code_verified_at",
                                           "source_code_verified_at"])
                return intent
            intent.attempts += 1
            if login_codes.attempts_exhausted(intent.attempts):
                _close(intent, Intent.State.EXPIRED, now)
            intent.save(update_fields=["attempts"])
            audit.record(survivor, "account.merge_proof_failed", target=survivor,
                              meta={"method": intent.method, "attempts": intent.attempts})
    raise MergeRefused(*failure)


def _check(intent, data, now):
    if intent.method == Intent.Method.CREDENTIALS:
        return _check_credentials(intent.source, data.get("password") or "", data.get("otp") or "")
    survivor_ok = login_codes.verify(intent.survivor_code_digest, data.get("survivor_code"), SURVIVOR, intent.pk)
    source_ok = intent.source is not None and login_codes.verify(
        intent.source_code_digest, data.get("source_code"), SOURCE, intent.pk)
    if not (survivor_ok and source_ok):
        return PROOF_FAILED, "One or both codes are wrong."
    intent.survivor_code_verified_at = intent.source_code_verified_at = now
    return None


def _check_credentials(source, password, otp):
    from apps.accounts.models_mfa import UserMFA
    from apps.accounts.services_mfa import consume_code

    if source is None:
        from apps.accounts.models import User
        User().set_password(password or "-")  # same hashing cost as a real check
        return PROOF_FAILED, "The account details are wrong."
    if not password or not source.check_password(password):
        return PROOF_FAILED, "The account details are wrong."
    factor = UserMFA.objects.select_for_update().filter(user=source, enabled_at__isnull=False).first()
    if factor is None:
        return (FACTOR_ENROLMENT_REQUIRED,
                "That account has no authenticator. Link it with emailed codes instead.")
    if not otp or not consume_code(factor, otp.strip()):
        return PROOF_FAILED, "The account details are wrong."
    return None


def resend(survivor, intent_id):
    now = timezone.now()
    with transaction.atomic():
        intent = locked_intent(survivor, intent_id)
        if intent.method != Intent.Method.EMAIL_CODES or not _live(intent, now):
            failure = (PROOF_EXPIRED, "This link request expired. Start again.")
        elif intent.resends >= MAX_RESENDS:
            failure = (PROOF_EXPIRED, "Too many codes were sent. Start again.")
        else:
            intent.resends += 1
            intent.save(update_fields=["resends"])
            codes = _issue(intent, now)
            failure = None
    if failure:
        raise MergeRefused(*failure)
    _send(intent, codes)
    return intent


def cancel(survivor, intent_id):
    now = timezone.now()
    with transaction.atomic():
        intent = locked_intent(survivor, intent_id)
        if intent.state in OPEN:
            _close(intent, Intent.State.CANCELLED, now)
            audit.record(survivor, "account.merge_cancelled", target=survivor, meta={"method": intent.method})
    return intent
