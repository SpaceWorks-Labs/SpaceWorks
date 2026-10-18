"""Canonical pre-approval claim bindings for the core financial upload transport."""
from django.utils import timezone
from apps.payments.event_payouts.errors import require
from apps.payments.event_payouts.attachment_models import FinanceAttachment
from .claim_models import ReimbursementClaim


def require_claim(*, event, owner_id, claim_uuid):
    row = ReimbursementClaim.objects.filter(uuid=claim_uuid, event=event, member_id=owner_id).first()
    require(row is not None, "not_found", status=404)
    due = row.info_due_at if row.state == "returned_for_info" else row.effective_due_at
    require(row.state in ("draft", "open", "returned_for_info") and due is not None
        and event.ends_at <= timezone.now() < due and event.status != "cancelled", "claim_closed")
    require(row.award.accepted_at is not None, "accepted_award_required")
    from .attendance import participating
    require(participating(row.award.request), "participation_not_accepted")
    return row


def metadata(asset):
    return {"asset_id": asset.pk, "generation": asset.generation, "version": asset.version,
        "filename": asset.original_filename,
        "state": asset.state, "sha256": asset.sha256, "bytes": asset.actual_bytes,
        "mime": asset.canonical_mime, "scan_status": asset.scan_status, "expires_at": asset.expires_at}


def owned_asset(*, event, owner_id, asset_id):
    row = FinanceAttachment.objects.filter(pk=asset_id, makerspace_id=event.makerspace_id,
        event_id_snapshot=event.pk, owner_member_id=owner_id, purpose="reimbursement_receipt", binding_kind="claim").first()
    require(row is not None and ReimbursementClaim.objects.filter(event=event, member_id=owner_id,
        uuid=row.binding_uuid).exists(), "not_found", status=404)
    return row


def create(*, request, event, data):
    claim = require_claim(event=event, owner_id=request.user.pk, claim_uuid=data["claim_uuid"])
    from apps.payments.event_payouts.attachment_workflow import create_claim_upload
    # Core re-enters the installed claim binding provider under domain locks before
    # persisting/promoting. This preflight alone never authorizes a final write.
    return create_claim_upload(request=request, event_id=event.pk, claim_uuid=claim.uuid, data=data)


def complete(*, request, event, asset_id, data):
    row = owned_asset(event=event, owner_id=request.user.pk, asset_id=asset_id)
    require_claim(event=event, owner_id=request.user.pk, claim_uuid=row.binding_uuid)
    from apps.payments.event_payouts.attachment_workflow import complete_claim_upload
    return complete_claim_upload(request=request, event_id=event.pk, asset_id=asset_id, data=data)


def delete(*, request, event, asset_id, data):
    row = owned_asset(event=event, owner_id=request.user.pk, asset_id=asset_id)
    require_claim(event=event, owner_id=request.user.pk, claim_uuid=row.binding_uuid)
    from apps.payments.event_payouts.attachment_workflow import delete_claim_upload
    return delete_claim_upload(request=request, event_id=event.pk, asset_id=asset_id, data=data)
