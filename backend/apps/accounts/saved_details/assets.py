"""Owner résumé lifecycle with account budget reservation and detached validation."""
from django.utils.translation import gettext
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from apps.audit.services import record
from apps.encryption.account_mappers import account_key_context
from apps.encryption.account_services import prepare_account_key
from apps.encryption.account_write_fence import account_write

from . import storage
from .access import require_owner
from .commands import remember, replay, request_digest
from .crypto import open_value, seal
from .errors import SavedDetailsError
from .models import MemberSavedAsset, MemberSavedDetail, SavedDetailsObjectCleanup
from .workflow import require_version


def owned_asset(actor_id, asset_id, *, lock=False):
    require_owner(actor_id)
    query = MemberSavedAsset.objects.select_for_update() if lock else MemberSavedAsset.objects
    row = query.filter(pk=asset_id, user_id=actor_id).first()
    if row is None:
        raise SavedDetailsError("not_found", gettext("Résumé not found."), 404)
    return row


def project(asset):
    result = {"asset_id": asset.pk, "state": asset.state, "sha256": asset.sha256, "bytes": asset.size_bytes,
              "version": asset.version, "generation": asset.generation}
    if asset.failure_code:
        result["code"] = asset.failure_code
    return result


def create_resume(actor_id, body, operation_id):
    require_owner(actor_id)
    if not isinstance(body.get("filename"), str) or not body["filename"].lower().endswith(".pdf") or len(body["filename"]) > 255 or body.get("mime") != "application/pdf":
        raise SavedDetailsError("invalid_pdf", gettext("Choose a PDF résumé."))
    size = body.get("bytes")
    if type(size) is not int or not 1 <= size <= storage.MAX_RESUME_BYTES:
        raise SavedDetailsError("asset_too_large", gettext("PDF résumés must be at most 10 MiB."), 413)
    digest = request_digest("resume-create", body)
    previous = replay(actor_id, operation_id, digest)
    key = prepare_account_key(actor_id)
    if previous is None:
        with account_write(actor_id), account_key_context(key):
            actor = require_owner(actor_id, lock=True)
            previous = replay(actor_id, operation_id, digest, key=key)
            if previous is None:
                used = MemberSavedAsset.objects.filter(user_id=actor_id).exclude(state="deleted").aggregate(n=Sum("size_bytes"))["n"] or 0
                limit = 50 * 1024**2
                if not getattr(settings, "PLATFORM_DOMAIN_SUFFIX", ""):
                    limit = max(limit, int(getattr(settings, "ACCOUNT_SAVED_ASSET_BUDGET_BYTES", limit)))
                if used + size > limit:
                    raise SavedDetailsError("account_asset_budget_exceeded", gettext("Delete an old résumé before uploading another."), 413)
                public_id = uuid4()
                prefix = f"account/{public_id}"
                asset = MemberSavedAsset.objects.create(user=actor, public_id=public_id, size_bytes=size,
                    object_key=f"{prefix}/resume.pdf", staging_key=f"staging/{prefix}/resume.pdf",
                    verification_key=f"verification/{prefix}/resume.pdf")
                record(actor, "account.saved_resume_created", target=asset, meta={"bytes": size})
                previous = remember(actor_id, operation_id, digest, {"asset_id": asset.pk}, key)
    asset = owned_asset(actor_id, previous["asset_id"])
    result = project(asset)
    if asset.state == "uploading":
        upload = storage.initialize(asset)
        result["upload"] = {"method": upload.method, "url": upload.url, "fields": dict(upload.fields), "expires_at": upload.expires_at.isoformat()}
    return result


def complete_resume(actor_id, asset_id, body):
    require_owner(actor_id)
    digest = request_digest(["resume-complete", asset_id], body)
    old = replay(actor_id, body["operation_id"], digest)
    if old is not None:
        return old
    key = prepare_account_key(actor_id)
    with account_write(actor_id), account_key_context(key):
        actor = require_owner(actor_id, lock=True)
        old = replay(actor_id, body["operation_id"], digest, key=key)
        if old is not None:
            return old
        asset = owned_asset(actor_id, asset_id, lock=True)
        require_version(asset.version, body["expected_version"])
        if asset.generation != body["generation"]:
            raise SavedDetailsError("upload_generation_changed", gettext("Restart this upload."), 409)
        if asset.state != "uploading":
            raise SavedDetailsError("asset_not_ready", gettext("This résumé is no longer accepting uploads."), 409)
        asset.state, asset.version = "validating", asset.version + 1
        asset.save(update_fields=["state", "version", "updated_at"])
        record(actor, "account.saved_resume_validation_requested", target=asset)
        return remember(actor_id, body["operation_id"], digest,
            {"asset_id": asset.pk, "state": "validating", "status_url": f"/api/v1/member/saved-details/resume-assets/{asset.pk}/"}, key)


def validate_resume(asset_id):
    """Periodic worker picks validating rows; broker/scanner/storage I/O is outside locks."""
    pending = MemberSavedAsset.objects.filter(pk=asset_id, state="validating").first()
    if pending is None:
        return
    claim = uuid4()
    with account_write(pending.user_id):
        actor = require_owner(pending.user_id, lock=True)
        asset = owned_asset(actor.pk, asset_id, lock=True)
        if asset.state != "validating" or (asset.claim_uuid and asset.updated_at > timezone.now() - timedelta(minutes=15)):
            return
        previous_keys = [asset.object_key, asset.verification_key]
        asset.cleanup_keys = sorted(set([*asset.cleanup_keys, *previous_keys]))
        asset.object_key = f"account/{asset.public_id}/{claim}/resume.pdf"
        asset.verification_key = f"verification/account/{asset.public_id}/{claim}/resume.pdf"
        asset.claim_uuid = claim
        asset.save(update_fields=["claim_uuid", "object_key", "verification_key", "cleanup_keys", "updated_at"])
        SavedDetailsObjectCleanup.objects.create(object_keys=previous_keys, next_attempt_at=timezone.now())
        record(actor, "account.saved_resume_validation_claimed", target=asset)
    try:
        result, code = storage.verify_resume(asset), ""
    except SavedDetailsError as exc:
        result, code = None, str(exc.detail["code"])
    with account_write(asset.user_id):
        actor = require_owner(asset.user_id, lock=True)
        current = owned_asset(actor.pk, asset_id, lock=True)
        if current.claim_uuid != claim or current.state != "validating":
            return  # deletion receipt repeatedly deletes every version, including late bytes
        if result:
            for name, value in result.items():
                setattr(current, name, value)
            current.state = "ready"
        elif code in {"storage_unavailable", "scanner_unavailable"}:
            current.claim_uuid = None  # safe retry, preserve reservation
        else:
            current.state = "failed"
        current.failure_code, current.version = code, current.version + 1
        current.save()
        record(actor, "account.saved_resume_validation_completed", target=current, meta={"state": current.state, "code": code})


def delete_resume(actor_id, asset_id, body):
    digest = request_digest(["resume-delete", asset_id], body)
    old = replay(actor_id, body["operation_id"], digest)
    if old is not None:
        return old
    key = prepare_account_key(actor_id)
    before = MemberSavedDetail.objects.filter(user_id=actor_id, field_key="resume", deleted_at__isnull=True).first()
    selected = open_value(before, "value_envelope") if before else None
    with account_write(actor_id), account_key_context(key):
        actor = require_owner(actor_id, lock=True)
        old = replay(actor_id, body["operation_id"], digest, key=key)
        if old is not None:
            return old
        asset = owned_asset(actor_id, asset_id, lock=True)
        require_version(asset.version, body["expected_version"])
        # Clear the current reference conservatively; no stale intent can restore
        # this asset because put_locked also checks current ready ownership.
        detail = MemberSavedDetail.objects.select_for_update().filter(user=actor, field_key="resume").first()
        if (detail.version if detail else 0) != (before.version if before else 0):
            raise SavedDetailsError("stale_version", gettext("Your saved résumé changed. Review it before deleting."), 409)
        if (detail and not detail.deleted_at and before and detail.version == before.version
                and selected and selected.get("asset_id") == asset.pk):
            detail.value_envelope = seal(None, detail, "value_envelope", key)
            detail.deleted_at, detail.version = timezone.now(), detail.version + 1
            detail.save()
            record(actor, "account.saved_detail_deleted", target=detail, meta={"field_key": "resume", "version": detail.version})
        asset.state, asset.version = "deleting", asset.version + 1
        asset.save(update_fields=["state", "version", "updated_at"])
        SavedDetailsObjectCleanup.objects.create(object_keys=list(set([asset.object_key, asset.staging_key, asset.verification_key, *asset.cleanup_keys])), next_attempt_at=timezone.now())
        record(actor, "account.saved_resume_deleted", target=asset)
        return remember(actor_id, body["operation_id"], digest, {"asset_id": asset.pk, "state": "deleting"}, key)
