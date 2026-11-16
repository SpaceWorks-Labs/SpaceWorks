"""Supervised provider evidence, never age-based recovery of uncertain allowance."""
import hashlib
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.operations.models import CloudEmailBudgetAccount, CloudEmailReservation
from apps.operations.cloud_quotas.operator import require_operator


def reconcile(*, reservation_id, actor, evidence):
    """Evidence is an operator-obtained provider receipt/support attestation.

    Provider absence from a search result is insufficient: nonacceptance must be
    explicitly confirmed for the exact attempt. Only its digest enters audit.
    """
    actor = require_operator(actor)
    required = {"version", "reservation_id", "outcome", "source", "reference", "observed_at", "attempt_key"}
    if not isinstance(evidence, dict) or not required <= evidence.keys() or evidence.keys() - required - {"provider_message_id"}:
        raise ValueError("email_reconciliation_evidence_invalid")
    if (type(evidence["version"]) is not int or evidence["version"] != 1
            or type(evidence["reservation_id"]) is not int or evidence["reservation_id"] != reservation_id):
        raise ValueError("email_reconciliation_identity_mismatch")
    outcome = evidence["outcome"]
    if outcome not in {"accepted", "confirmed_not_accepted"} or evidence["source"] not in {"provider_receipt", "provider_support"}:
        raise ValueError("email_reconciliation_requires_provider_evidence")
    if not isinstance(evidence["reference"], str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", evidence["reference"]):
        raise ValueError("email_reconciliation_reference_invalid")
    observed = datetime.fromisoformat(evidence["observed_at"])
    if observed.tzinfo is None or observed > timezone.now():
        raise ValueError("email_reconciliation_observation_invalid")
    digest = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
    seed = CloudEmailReservation.objects.get(pk=reservation_id)
    with transaction.atomic():
        account = CloudEmailBudgetAccount.objects.select_for_update().get(pk=seed.account_id)
        row = CloudEmailReservation.objects.select_for_update().get(pk=reservation_id)
        if row.attempt_key != evidence["attempt_key"] or observed < row.created_at:
            raise ValueError("email_reconciliation_identity_mismatch")
        if row.state not in {"reserved", "uncertain"}:
            raise ValueError("email_reconciliation_already_settled")
        row.state = "accepted" if outcome == "accepted" else "released"
        if row.state == "accepted":
            message_id = evidence.get("provider_message_id")
            if not isinstance(message_id, str) or not 1 <= len(message_id) <= 200 or any(c in message_id for c in "\r\n"):
                raise ValueError("email_reconciliation_message_identity_required")
            row.provider_message_id = message_id
            day = observed.astimezone(ZoneInfo(account.reset_timezone)).date()
            row.accepted_day, row.accepted_month = day, day.replace(day=1)
        row.save()
        if row.log_id:
            from apps.integrations.models import EmailLog
            log = EmailLog.objects.select_for_update().get(pk=row.log_id)
            if log.makerspace_id:
                from apps.tenant_migration.gate_runtime import assert_write_allowed
                assert_write_allowed(log.makerspace_id)
            from apps.encryption.write_fence import assert_mapped_write_allowed
            assert_mapped_write_allowed(log.makerspace_id)
            if row.state == "accepted":
                log.status, log.email_retryable = EmailLog.Status.SENT, False
                log.provider_name, log.provider_message_id = row.provider, row.provider_message_id
            else:
                # Re-arm only persistent source-owned mail, never expired OTPs.
                from apps.integrations.delivery_sources import has_retry_content
                log.email_retryable = has_retry_content(log)
                log.email_retry_at = timezone.now()
                log.status = EmailLog.Status.FAILED
                _release_personal_claim(log)
            log.error = "email_operator_reconciled"
            log.save()
            if row.state == "accepted":
                from apps.integrations.delivery_sources import finished
                transaction.on_commit(lambda: finished(log), robust=True)
        audit.record(actor, "email.acceptance_reconciled", target=row,
            meta={"reservation_id": row.pk, "outcome": outcome, "evidence_sha256": digest,
                  "evidence_source": evidence["source"]})
    return row.state


def _release_personal_claim(log):
    if log.source_kind != "notification.envelope":
        return
    from apps.integrations.models_contract import NotificationDelivery
    rows = NotificationDelivery.objects.select_for_update().filter(pk=log.source_metadata.get("delivery_id"),
        envelope_id=log.source_id, makerspace_id=log.makerspace_id, envelope__recipient_id=log.recipient_id,
        channel="email", state__in=["retrying", "failed"])
    row = rows.first()
    if row is not None:
        row.state, row.retryable, row.claim_until = "retrying", True, None
        row.next_attempt_at, row.last_error = timezone.now(), "email_deferred"
        row.save(update_fields=["state", "retryable", "claim_until", "next_attempt_at", "last_error", "updated_at"])
