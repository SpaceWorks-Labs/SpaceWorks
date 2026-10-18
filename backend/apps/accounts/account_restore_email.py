"""A synchronous, non-persisted restore link using the existing reset queue."""

from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts import audit_events
from apps.accounts.account_restore import matches, restore_locked
from apps.accounts.models import PasswordResetEnvelopeStatus
from apps.accounts.password_reset_crypto import normalize_email, new_dummy_digest
from apps.accounts.recovery_locks import locked_proof


def send_restore_link(recipient, token):
    from apps.integrations.dispatch import dispatch_email
    base = settings.PUBLIC_APP_BASE_URL.rstrip("/")
    if not base:
        return False
    url = base + "/account/restore#" + urlencode({"email": recipient, "token": token})
    log = dispatch_email(
        to_email=recipient, subject="Restore your Space Works account",
        text_body="Your account is archived. To restore it and choose a new password, open:\n\n"
                  + url + "\n\nThis link works once, for 24 hours, before identity removal begins. "
                  "Memberships and previous sessions remain revoked. If you did not request this, ignore this email.",
        stream="account", event="account_restore", audience="user", connection="platform",
        persist_body=False, sync=True,
    )
    return log.status == log.Status.SENT


def confirm_email(email, token, new_password):
    normalized, now = normalize_email(email), timezone.now()
    restored, failure = None, None
    with transaction.atomic():
        row, user, equal = locked_proof(normalized, token, purpose="restore", now=now)
        now = timezone.now()
        attempts = row.attempts if row else 5
        if row:
            row.attempts = min(5, attempts + 1)
            row.save(update_fields=["attempts"])
        audit_events.record_auth_event(None, "auth.account_restore_attempted", target=row)
        valid = (row and user and equal and row.purpose == "restore" and row.digest_is_live
                 and row.status == PasswordResetEnvelopeStatus.ISSUED and not row.consumed_at
                 and row.expires_at and row.expires_at > now and attempts < 5)
        if valid:
            if matches(user, row.credential_fingerprint):
                try:
                    restored = restore_locked(user, fingerprint=row.credential_fingerprint, new_password=new_password)
                except ValidationError as exc:
                    failure = exc
                else:
                    row.status, row.consumed_at, row.terminal_at = PasswordResetEnvelopeStatus.CONSUMED, now, now
                    row.digest, row.digest_is_live = new_dummy_digest(normalized), False
                    row.save(update_fields=["status", "consumed_at", "terminal_at", "digest", "digest_is_live"])
    if failure:
        raise failure
    if restored is None:
        raise ValidationError({"detail": "Invalid or expired restore proof."})
    return restored
