"""Lease-fenced, at-most-once issuance drain for password reset envelopes."""

import logging
import os
import socket
import uuid
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import PasswordResetEnvelope, PasswordResetEnvelopeStatus, User
from apps.accounts.password_reset_context import (
    lock_recovery_account, recoverable, reset_destination, recovery_transaction,
)
from apps.integrations.email import platform_email_configured
from apps.accounts.account_restore import restorable, identifier_fingerprint
from apps.accounts.account_restore_email import send_restore_link
from apps.accounts.password_reset_crypto import (
    credential_fingerprint,
    generate_otp,
    new_dummy_digest,
    otp_digest,
)
from apps.accounts.services_password_reset_maintenance import (
    discard_expired_issued,
    expire_delivery_leases,
)
from apps.integrations.email import email_enabled, send_password_reset_otp

logger = logging.getLogger(__name__)

CHALLENGE_TTL = timedelta(minutes=10)
CLAIM_LEASE = timedelta(minutes=5)
DEFAULT_BATCH_SIZE = 50


@dataclass(frozen=True)
class EnvelopeClaim:
    envelope_id: int
    generation: int
    email_normalized: str


@dataclass(frozen=True)
class DeliveryAttempt:
    claim: EnvelopeClaim
    recipient: str
    code: str
    reset_url: str = ""
    account_label: str = ""
    restore: bool = False


def drain_password_reset_envelopes(*, batch_size=DEFAULT_BATCH_SIZE, owner=None):
    """Resolve, mint and synchronously deliver one bounded claimed batch."""
    expire_delivery_leases(batch_size=batch_size)
    discard_expired_issued(batch_size=batch_size)
    claims = claim_pending_envelopes(batch_size=batch_size, owner=owner)
    outcomes = {"claimed": len(claims), "issued": 0, "terminal": 0, "stale": 0}
    for claim in claims:
        attempt = prepare_delivery(claim)
        if attempt is None:
            outcomes["stale"] += 1
            continue
        if isinstance(attempt, str):
            outcomes["terminal"] += 1
            continue
        delivered = False
        try:
            # The digest and `delivering` state committed before this SMTP call. This
            # call must remain synchronous and outside every row-lock transaction.
            recovery_details = ({"reset_url": attempt.reset_url, "account_label": attempt.account_label}
                                if attempt.reset_url else {})
            delivered = bool(
                send_restore_link(attempt.recipient, attempt.code) if attempt.restore else send_password_reset_otp(
                    attempt.recipient,
                    attempt.code,
                    expires_in_minutes=int(CHALLENGE_TTL.total_seconds() // 60),
                    **recovery_details,
                )
            )
        except Exception:  # provider failure is terminal but never crashes the drain
            logger.exception(
                "password_reset_delivery_failed",
                extra={"envelope_id": claim.envelope_id},
            )
        if finalize_delivery(claim, delivered=delivered):
            outcomes["issued" if delivered else "terminal"] += 1
        else:
            outcomes["stale"] += 1
    logger.info("password_reset_drain_complete", extra=outcomes)
    return outcomes


def claim_pending_envelopes(*, batch_size=DEFAULT_BATCH_SIZE, owner=None, now=None):
    claimed_at = now or timezone.now()
    claim_owner = (owner or _worker_identity())[:128]
    with transaction.atomic():
        rows = list(
            PasswordResetEnvelope.objects.select_for_update(skip_locked=True)
            .filter(
                Q(status=PasswordResetEnvelopeStatus.PENDING)
                | Q(
                    status=PasswordResetEnvelopeStatus.CLAIMED,
                    claim_expires_at__lte=claimed_at,
                )
            )
            .order_by("requested_at", "pk")[:batch_size]
        )
        claims = []
        for row in rows:
            row.status = PasswordResetEnvelopeStatus.CLAIMED
            row.claimed_at = claimed_at
            row.claim_owner = claim_owner
            row.claim_expires_at = claimed_at + CLAIM_LEASE
            row.generation += 1
            row.save(
                update_fields=[
                    "status",
                    "claimed_at",
                    "claim_owner",
                    "claim_expires_at",
                    "generation",
                ]
            )
            claims.append(
                EnvelopeClaim(row.pk, row.generation, row.email_normalized)
            )
    return claims


def prepare_delivery(claim, *, now=None):
    """Commit the digest and delivering state, returning the in-memory secret."""
    issued_at = now or timezone.now()
    snapshot = PasswordResetEnvelope.objects.filter(pk=claim.envelope_id).first()
    if snapshot is None:
        return None
    account = User.objects.filter(pk=snapshot.user_id).first()
    if account is None:
        return None
    with recovery_transaction(account):
        user = lock_recovery_account(account)
        envelope = (
            PasswordResetEnvelope.objects.select_for_update()
            .filter(
                pk=claim.envelope_id,
                generation=claim.generation,
                status=PasswordResetEnvelopeStatus.CLAIMED,
            )
            .first()
        )
        if envelope is None:
            return None
        if user is None or envelope.email_normalized != claim.email_normalized or envelope.user_id != user.pk:
            return None
        slug = envelope.makerspace.slug if envelope.makerspace_id else None
        archived = bool(envelope.context == "member" and user.account_kind == "member"
                        and restorable(user, now=issued_at))
        if (not archived and (not recoverable(user, context=envelope.context, makerspace=slug,
                                             origin=envelope.request_origin)
                              or user.deletion_requested_at is not None)
                or envelope.context != user.account_kind
                or envelope.makerspace_id != (user.staff_makerspace_id if user.account_kind == "staff" else None)
                or user.email.strip().lower() != envelope.email_normalized
                or user.credential_generation != envelope.credential_generation
                or user.account_restored_at and envelope.requested_at <= user.account_restored_at):
            return _finish_claimed_terminal(
                envelope, claim, PasswordResetEnvelopeStatus.DISCARDED, issued_at
            )
        # Availability is re-checked where issuance actually occurs. The deployment-level
        # request-time gate alone is insufficient because configuration may change in queue.
        if not (email_enabled() if envelope.context == "member" else platform_email_configured()):
            return _finish_claimed_terminal(
                envelope, claim, PasswordResetEnvelopeStatus.UNDELIVERABLE, issued_at
            )

        code = secrets.token_urlsafe(48) if archived else generate_otp()
        updated = PasswordResetEnvelope.objects.filter(
            pk=envelope.pk,
            generation=claim.generation,
            status=PasswordResetEnvelopeStatus.CLAIMED,
        ).update(
            user=user,
            purpose="restore" if archived else "reset",
            digest=otp_digest(code, envelope.email_normalized),
            digest_is_live=True,
            credential_fingerprint=identifier_fingerprint(user) if archived else credential_fingerprint(
                user, envelope.email_normalized
            ),
            expires_at=issued_at + (timedelta(hours=24) if archived else CHALLENGE_TTL),
            consumed_at=None,
            attempts=0,
            status=PasswordResetEnvelopeStatus.DELIVERING,
            claim_expires_at=issued_at + CLAIM_LEASE,
            terminal_at=None,
            superseded_at=None,
        )
        if updated != 1:
            return None
        # Resolve trusted routing while the tenant is locked.
        url, label = reset_destination(user) if envelope.context != "member" else ("", "")
    return DeliveryAttempt(claim, envelope.email_normalized, code, url, label, restore=archived)


def finalize_delivery(claim, *, delivered, now=None):
    """Fence the SMTP result against lease expiry or a newer claim generation."""
    finished_at = now or timezone.now()
    filters = {
        "pk": claim.envelope_id,
        "generation": claim.generation,
        "status": PasswordResetEnvelopeStatus.DELIVERING,
    }
    if delivered:
        updated = PasswordResetEnvelope.objects.filter(**filters).update(
            status=PasswordResetEnvelopeStatus.ISSUED,
            claimed_at=None,
            claim_owner="",
            claim_expires_at=None,
        )
    else:
        updated = PasswordResetEnvelope.objects.filter(**filters).update(
            status=PasswordResetEnvelopeStatus.UNDELIVERABLE,
            digest=new_dummy_digest(claim.email_normalized),
            digest_is_live=False,
            credential_fingerprint="",
            expires_at=None,
            terminal_at=finished_at,
            claimed_at=None,
            claim_owner="",
            claim_expires_at=None,
        )
    return updated == 1


def _finish_claimed_terminal(envelope, claim, status, now):
    updated = PasswordResetEnvelope.objects.filter(
        pk=envelope.pk,
        generation=claim.generation,
        status=PasswordResetEnvelopeStatus.CLAIMED,
    ).update(
        status=status,
        digest=new_dummy_digest(envelope.email_normalized),
        digest_is_live=False,
        credential_fingerprint="",
        expires_at=None,
        terminal_at=now,
        claimed_at=None,
        claim_owner="",
        claim_expires_at=None,
    )
    return status if updated == 1 else None


def _worker_identity():
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex}"
