"""Durable Apple revocation, queued at departure and swept daily until terminal."""

import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.apple_credentials import apple_post, client_secret
from apps.accounts.models import User
from apps.accounts.models_account_purge import AppleRefreshCredential, AppleRevocation
from apps.audit import services as audit
from apps.makerspaces.secrets import decrypt_value

logger = logging.getLogger(__name__)


def schedule_revocations(user):
    """Called with the Stage A User lock; work rows commit with the departure."""
    credentials = AppleRefreshCredential.objects.filter(social_identity__user=user)
    found = False
    for credential in credentials:
        found = True
        snapshot_credential(user, credential)
    if not found and user.social_identities.filter(provider="apple").exists():
        AppleRevocation.objects.get_or_create(user=user, client_id="", credential_version=None)
        found = True
    if found:
        transaction.on_commit(lambda: _enqueue(user.pk), robust=True)


def snapshot_credential(user, credential):
    return AppleRevocation.objects.get_or_create(
        user=user, client_id=credential.client_id, credential_version=credential.version,
        defaults={"credential_id": credential.pk, "token_ciphertext": credential.token_ciphertext,
                  "created_at": user.deletion_requested_at or timezone.now()},
    )[0]


def _enqueue(user_id):
    try:
        from apps.accounts.tasks import revoke_apple_tokens_task
        revoke_apple_tokens_task.delay(user_id)
    except Exception as exc:
        logger.warning("apple_revocation_enqueue_failed", extra={
            "user_id": user_id, "error_type": type(exc).__name__,
        })


def revoke_one(pk):
    # Global credential operation: no tenant row is changed. User-before-work-row
    # serializes against Stage A, credential replacement and final identity purge.
    user_id = AppleRevocation.objects.values_list("user_id", flat=True).get(pk=pk)
    with transaction.atomic():
        user = User.objects.select_for_update(no_key=True).get(pk=user_id)
        row = AppleRevocation.objects.select_for_update().get(pk=pk)
        now = timezone.now()
        if row.done_at:
            return
        expired = now >= row.created_at + timedelta(days=80)
        if not expired and row.next_attempt_at and row.next_attempt_at > now:
            return
        if expired or not row.token_ciphertext:
            row.done_at = now
            row.token_ciphertext = ""
            row.last_error = "retention_deadline" if expired else "credential_unavailable"
            row.save(update_fields=["done_at", "last_error", "token_ciphertext"])
            audit.record(None, "account.apple_revocation_unavailable", target=user,
                         meta={"reason": row.last_error})
            return
        row.attempts += 1
        try:
            apple_post("/auth/revoke", {
                "client_id": row.client_id, "client_secret": client_secret(row.client_id),
                "token": decrypt_value(row.token_ciphertext), "token_type_hint": "refresh_token",
            })
        except Exception as exc:
            row.last_error = type(exc).__name__[:128]
            row.next_attempt_at = now + timedelta(minutes=min(24 * 60, 5 * 2 ** min(row.attempts, 9)))
            logger.warning("apple_revocation_failed", extra={"user_id": user.pk, "attempt": row.attempts,
                                                          "error_type": type(exc).__name__})
            audit.record(None, "account.apple_revocation_retry", target=user, meta={"attempts": row.attempts})
        else:
            row.done_at = now
            row.last_error = ""
            row.next_attempt_at = None
            AppleRefreshCredential.objects.filter(pk=row.credential_id, version=row.credential_version).delete()
            audit.record(None, "account.apple_revoked", target=user)
        if row.done_at:
            row.token_ciphertext = ""
        row.save(update_fields=["attempts", "last_error", "next_attempt_at", "done_at", "token_ciphertext"])


def sweep_revocations(user_id=None):
    # Also recover pre-upgrade Stage A departures that had no work-row code yet.
    archived = User.objects.filter(deletion_requested_at__isnull=False, account_purged_at__isnull=True)
    if user_id is not None:
        archived = archived.filter(pk=user_id)
    for pk in archived.values_list("pk", flat=True).iterator():
        with transaction.atomic():
            user = User.objects.select_for_update(no_key=True).get(pk=pk)
            if not AppleRevocation.objects.filter(user=user).exists():
                schedule_revocations(user)
    rows = AppleRevocation.objects.filter(done_at__isnull=True).filter(
        Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=timezone.now())
        | Q(created_at__lte=timezone.now() - timedelta(days=80)),
    )
    if user_id is not None:
        rows = rows.filter(user_id=user_id)
    for pk in rows.values_list("pk", flat=True).iterator():
        try:
            revoke_one(pk)
        except Exception as exc:
            logger.warning("apple_revocation_work_failed", extra={"revocation_id": pk,
                                                                "error_type": type(exc).__name__})
