"""Secret-bearing mail and SMS (OTPs, reset links, invitations) sent by a Celery worker, not the web request.

These messages are deliberately never stored (``persist_body=False``): the stored row is redacted. To still leave
the request cycle, the body is *sealed* (Fernet, short TTL) into the task arguments, so the broker only ever holds
ciphertext that expires within minutes; the redacted ``EmailLog`` row carries status, attempts and errors.

Stays inline (documented exceptions): Celery eager mode (tests, brokerless), the free deployment profile (no
worker; tick drain), code already inside a worker, and the explicit admin "send a test email now" action.
"""
import base64
import json
import logging
import time

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)

TTL_SECONDS = 15 * 60
INLINE_EVENTS = frozenset({"email_test"})  # explicit operator test sends stay synchronous
ACCEPTED = frozenset({"sent", "delivered", "pending", "sending"})


def accepted(log) -> bool:
    """True when a transient send was delivered OR handed to the worker (callers cannot tell the difference)."""
    return getattr(log, "status", "") in ACCEPTED


def queue_allowed(event="") -> bool:
    from celery import current_task
    from .mail_providers.budget_config import free_profile
    if event in INLINE_EVENTS or free_profile() or getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        return False
    if current_task and getattr(current_task.request, "id", None):
        return False
    return bool(getattr(settings, "TRANSIENT_MESSAGES_VIA_CELERY", True))


INFO = b"spaceworks/transient-mail/v1"


def _derive(secret: str) -> Fernet:
    """A dedicated key per purpose: HKDF-SHA256 over the deployment secret with a distinct info label, so this key
    is never the SECRET_KEY / API_CLIENT_ENC_KEY itself and cannot decrypt (or be confused with) any other sealed data."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    raw = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=INFO).derive(secret.encode())
    return Fernet(base64.urlsafe_b64encode(raw))


def _ring() -> MultiFernet:
    """Current key first (encrypts), then the previous ones (decrypt only) so a rotation never strands queued mail.

    Current: ``TRANSIENT_MAIL_KEY`` when set, else ``SECRET_KEY``. Previous: ``TRANSIENT_MAIL_KEY_PREVIOUS`` and
    Django's ``SECRET_KEY_FALLBACKS``. Messages live at most TTL_SECONDS, so keep the old key for one deploy.
    """
    current = getattr(settings, "TRANSIENT_MAIL_KEY", "") or settings.SECRET_KEY
    previous = [getattr(settings, "TRANSIENT_MAIL_KEY_PREVIOUS", "") or "", *getattr(settings, "SECRET_KEY_FALLBACKS", [])]
    secrets = [current, *(value for value in previous if value and value != current)]
    return MultiFernet([_derive(value) for value in secrets])


def seal(payload: dict) -> str:
    return _ring().encrypt(json.dumps(payload).encode()).decode()


def unseal(token: str):
    try:
        return json.loads(_ring().decrypt(token.encode(), ttl=TTL_SECONDS).decode())
    except (InvalidToken, ValueError):
        return None


def queue_email(log, *, to_email, subject, text_body, html_body="") -> bool:
    """Hand a redacted-row email to the worker. False means: caller delivers inline as before."""
    from .models_email import EmailLog
    if log.status != EmailLog.Status.PENDING or not queue_allowed(log.event):
        return False
    sealed = seal({"to": to_email, "subject": subject, "text": text_body, "html": html_body, "t": time.time()})
    transaction.on_commit(lambda lid=log.pk: _publish_email(lid, sealed), robust=True)
    return True


def _publish_email(log_id, sealed):
    from .models_email import EmailLog
    from .smtp_validation import sanitize_email_error
    from .tasks_transient import deliver_transient_email_task
    try:
        deliver_transient_email_task.delay(log_id, sealed)
    except Exception as exc:
        EmailLog.objects.filter(pk=log_id, status=EmailLog.Status.PENDING).update(
            status=EmailLog.Status.FAILED, error=sanitize_email_error(exc))
        logger.error("transient_email_enqueue_failed",
                     extra={"email_log_id": log_id, "error_class": type(exc).__name__})


def queue_sms(*, to, body, purpose="authentication") -> bool:
    if not queue_allowed():
        return False
    sealed = seal({"to": to, "body": body, "purpose": purpose, "t": time.time()})
    transaction.on_commit(lambda: _publish_sms(sealed), robust=True)
    return True


def _publish_sms(sealed):
    from .tasks_transient import deliver_transient_sms_task
    try:
        deliver_transient_sms_task.delay(sealed)
    except Exception as exc:
        logger.error("transient_sms_enqueue_failed", extra={"error_class": type(exc).__name__})
