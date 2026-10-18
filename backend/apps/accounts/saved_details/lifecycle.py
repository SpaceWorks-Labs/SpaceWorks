"""Reviewed erasure adapter and repeatable all-version object cleanup."""
from datetime import timedelta
import logging

from django.utils import timezone

from apps.audit.services import record
from apps.encryption.account_services import revoke_account_keys
from apps.encryption.account_write_fence import account_write

from . import storage
from .access import require_owner
from .models import (
    AccountSavedDetailsExportJob, MemberSavedAsset, MemberSavedDetail,
    SavedDetailCommandReceipt, SavedDetailUpdateIntent, SavedDetailsObjectCleanup,
)

logger = logging.getLogger(__name__)


def erase_account_vault(user_id, *, actor):
    """Called ONLY by the reviewed account-erasure workflow before User removal.

    Independently submitted event sources/copies are deliberately outside this
    account adapter. The caller owns account deletion authorization and confirms
    the disclosure that submitted evidence follows its separate retention policy.
    """
    from apps.encryption.account_models import PiiAccountWriteFence
    if PiiAccountWriteFence.objects.filter(user_id=user_id, state="erased").exists():
        return  # successful prior erasure retained only FK-free cleanup receipts
    with account_write(user_id, exclusive=True):
        from apps.accounts.models import User
        from apps.encryption.account_models import AccountPiiKey, PiiAccountWriteFence
        owner = User.objects.select_for_update().get(pk=user_id)
        PiiAccountWriteFence.objects.get_or_create(user_id=user_id)
        list(AccountPiiKey.objects.select_for_update().filter(user_id=user_id).order_by("version"))
        assets = list(MemberSavedAsset.objects.select_for_update().filter(user_id=user_id).order_by("pk"))
        jobs = list(AccountSavedDetailsExportJob.objects.select_for_update().filter(user_id=user_id).order_by("pk"))
        keys = [key for asset in assets for key in (asset.object_key, asset.staging_key, asset.verification_key)]
        keys.extend(key for asset in assets for key in asset.cleanup_keys)
        keys.extend(job.object_key for job in jobs)
        keys.extend(key for job in jobs for key in job.cleanup_keys)
        if keys:
            SavedDetailsObjectCleanup.objects.create(object_keys=keys, next_attempt_at=timezone.now())
        # Epoch is revoked before releasing the fence; all later prepared intent
        # insertions fail. Rows are erased in this same transaction.
        SavedDetailUpdateIntent.objects.filter(user_id=user_id).delete()
        SavedDetailCommandReceipt.objects.filter(user_id=user_id).delete()
        MemberSavedDetail.objects.filter(user_id=user_id).delete()
        MemberSavedAsset.objects.filter(user_id=user_id).delete()
        AccountSavedDetailsExportJob.objects.filter(user_id=user_id).delete()
        revoke_account_keys(user_id, actor=actor, erase=True)
        record(actor, "account.saved_details_erased", target=owner)


def run_object_cleanup(receipt_id):
    receipt = SavedDetailsObjectCleanup.objects.filter(pk=receipt_id).first()
    if receipt is None or receipt.next_attempt_at > timezone.now():
        return
    try:
        storage.delete_keys(receipt.object_keys)
    except Exception:
        # Never log private object keys or owner values. Keep durable retry data.
        logger.warning("Account object cleanup requires retry", extra={"cleanup_id": str(receipt_id)})
        SavedDetailsObjectCleanup.objects.filter(pk=receipt_id).update(next_attempt_at=timezone.now() + timedelta(hours=12))
        return
    SavedDetailsObjectCleanup.objects.filter(pk=receipt_id).update(
        completed_at=timezone.now(), next_attempt_at=timezone.now() + timedelta(hours=6))
    # Re-delete indefinitely: a pre-erasure worker/presign may finish late.
    owners = MemberSavedAsset.objects.filter(
        object_key__in=receipt.object_keys, state="deleting",
    ).values_list("user_id", flat=True).distinct()
    for user_id in sorted(owners):
        with account_write(user_id):
            from apps.accounts.models import User
            actor = User.objects.select_for_update().filter(pk=user_id).first()
            if actor is None:
                continue  # account erasure already removed its live asset rows
            assets = MemberSavedAsset.objects.select_for_update().filter(
                user_id=user_id, object_key__in=receipt.object_keys, state="deleting",
            ).order_by("pk")
            for asset in assets:
                asset.state, asset.version = "deleted", asset.version + 1
                asset.save(update_fields=["state", "version", "updated_at"])
                record(actor, "account.saved_resume_cleanup_completed", target=asset)


def expire_exports():
    for job in AccountSavedDetailsExportJob.objects.filter(expires_at__lte=timezone.now()).exclude(state="expired"):
        with account_write(job.user_id):
            from apps.accounts.models import User
            actor = User.objects.select_for_update().get(pk=job.user_id)
            current = AccountSavedDetailsExportJob.objects.select_for_update().get(pk=job.pk)
            if current.state == "expired":
                continue
            SavedDetailsObjectCleanup.objects.create(object_keys=list(set([current.object_key, *current.cleanup_keys])), next_attempt_at=timezone.now())
            current.state = "expired"
            current.save(update_fields=["state"])
            record(actor, "account.saved_details_export_expired", target=current)


def expire_intents_and_receipts():
    """No decryption/key broker required to remove expired payloads."""
    pending = SavedDetailUpdateIntent.objects.filter(state="pending", expires_at__lte=timezone.now())
    for candidate in pending:
        with account_write(candidate.user_id):
            from apps.accounts.models import User
            actor = User.objects.select_for_update().get(pk=candidate.user_id)
            row = SavedDetailUpdateIntent.objects.select_for_update().get(pk=candidate.pk)
            if row.state != "pending":
                continue
            row.state, row.failure_code = "failed", "save_intent_expired"
            row.encrypted_payload, row.completed_at = "", timezone.now()
            row.field_status = {name: {"state": "failed", "code": row.failure_code} for name in row.chosen_fields}
            row.save(update_fields=["state", "failure_code", "encrypted_payload", "completed_at", "field_status"])
            record(actor, "account.saved_detail_intent_expired", target=row)
    # Completed payloads are erased on completion, earlier than the 24h ceiling.
    stale_receipt_owners = SavedDetailCommandReceipt.objects.filter(created_at__lt=timezone.now() - timedelta(days=30)).values_list("user_id", flat=True)
    stale_intent_owners = SavedDetailUpdateIntent.objects.filter(completed_at__lt=timezone.now() - timedelta(days=30)).values_list("user_id", flat=True)
    for user_id in sorted(set(stale_receipt_owners) | set(stale_intent_owners)):
        with account_write(user_id):
            SavedDetailCommandReceipt.objects.filter(user_id=user_id, created_at__lt=timezone.now() - timedelta(days=30)).delete()
            SavedDetailUpdateIntent.objects.filter(user_id=user_id, completed_at__lt=timezone.now() - timedelta(days=30)).delete()
