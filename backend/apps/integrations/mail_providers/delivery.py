"""Delivery receipt/idempotency and free-only budget admission."""

import hashlib
import json
import time
from contextvars import ContextVar

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.conf import settings
from django.db import connection

from .budget import BudgetDeferred, reserve, settle
from .budget_config import account_budget, free_profile

# Tick caller uses delivery_deadline; this is context-local, never a resident thread.
deadline = ContextVar("mail_deadline", default=None)
execution_guard = ContextVar("mail_execution_guard", default=None)


def delivery_timeout():
    from apps.integrations.smtp_validation import smtp_timeout_seconds
    limit = deadline.get()
    if not free_profile() or limit is None:
        return smtp_timeout_seconds()
    remaining = limit - time.monotonic() - 1
    if remaining < 1:
        raise BudgetDeferred("email_tick_budget_exhausted")
    return min(smtp_timeout_seconds(), remaining)


def definite_nonacceptance(exc):
    # Timeouts, disconnects and server errors may have accepted a message. Never
    # return that allowance without proof. Only explicit rejection is released.
    status = getattr(exc, "status_code", None)
    if type(status) is int and status in {400, 401, 403, 404, 413, 422, 429}:
        return True
    import smtplib
    try:
        from anymail.exceptions import AnymailInvalidAddress, AnymailUnsupportedFeature, AnymailSerializationError
        if isinstance(exc, (AnymailInvalidAddress, AnymailUnsupportedFeature, AnymailSerializationError)):
            return True  # Payload construction failed before any request.
    except ImportError:
        pass  # Legacy SMTP installations do not import/require Anymail.
    return isinstance(exc, (smtplib.SMTPRecipientsRefused, smtplib.SMTPAuthenticationError,
                            smtplib.SMTPSenderRefused, ImproperlyConfigured, ValidationError))


def provider_message_id(message):
    value = getattr(message, "spaceworks_provider_message_id", "")
    if not value:
        value = getattr(getattr(message, "anymail_status", None), "message_id", "")
    return value[:200] if isinstance(value, str) else ""


def send(log, message):
    if free_profile() and connection.in_atomic_block:
        # A nested atomic block would retain the account lock until its outer
        # caller commits, including throughout the remote send.
        raise ImproperlyConfigured("Free email must be sent after transaction commit.")
    # Resend retries retain content identity even as transport attempt count changes.
    message.message()  # Boundary validation before reserving any allowance.
    attachments = []
    for item in message.attachments:
        if hasattr(item, "filename"):
            data = item.content.encode() if isinstance(item.content, str) else item.content
            attachments.append((item.filename, item.mimetype, hashlib.sha256(data).hexdigest()))
        else:
            attachments.append(hashlib.sha256(item.as_bytes()).hexdigest())
    canonical = [message.subject, message.body, message.from_email, message.to,
                 message.cc, message.bcc, message.reply_to, message.extra_headers,
                 list(getattr(message, "alternatives", ())), attachments]
    content_key = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
    identity = f"{log.pk}:{log.retry_generation}:{log.attempts}:{content_key}"
    message.spaceworks_idempotency_key = "sw-" + hashlib.sha256(
        f"{getattr(settings, 'SPACEWORKS_DEPLOYMENT_ID', '')}:{log.pk}:{log.retry_generation}:{content_key}".encode()).hexdigest()
    receipt = None
    if free_profile():
        guard = execution_guard.get()
        if guard:
            guard()
        config = getattr(message.connection, "spaceworks_mail_config", None)
        if config is None:
            raise ImproperlyConfigured("Free mail requires an explicit account transport.")
        receipt = reserve(account_budget(config), log=log, attempt_key=identity,
                          recipients=len(message.recipients()))
        if receipt.state == "accepted":
            message.spaceworks_provider_message_id = receipt.provider_message_id
            return 1  # Recovery after provider acceptance but before EmailLog save.
    try:
        if free_profile() and execution_guard.get():
            execution_guard.get()()
        count = message.send()
    except Exception as exc:
        if receipt:
            settle(receipt, "released" if definite_nonacceptance(exc) else "uncertain", log=log)
        raise
    if receipt:
        settle(receipt, "accepted" if count else "released", log=log,
               provider_message_id=provider_message_id(message))
    if count != 1:
        raise RuntimeError("email_provider_did_not_accept_message")
    return count
