"""Owner claim-receipt upload commands: R claim locks around the core finance transport.

The claim binding is re-checked under the event and claim locks before core persists or
finalizes anything; the staging presign is issued only after the transaction commits,
so no storage I/O runs under a row lock. Core never imports this module.
"""
from apps.payments.event_payouts import attachment_uploads, attachment_processing, attachment_workflow
from apps.payments.event_payouts.attachment_models import FinanceAttachment
from apps.payments.event_payouts.errors import require
from .claim_models import ReimbursementClaim
from .receipt_uploads import metadata, require_claim
from .transactions import command


def _locked_claim(ctx, claim_uuid):
    claim = ReimbursementClaim.objects.select_for_update().filter(uuid=claim_uuid, event=ctx.event,
        member=ctx.actor).first()
    require(claim is not None, "not_found", status=404)
    require_claim(event=ctx.event, owner_id=ctx.actor.pk, claim_uuid=claim.uuid)
    return claim


def _locked_asset(ctx, asset_id):
    row = FinanceAttachment.objects.select_for_update().filter(pk=asset_id, makerspace_id=ctx.event.makerspace_id,
        event_id_snapshot=ctx.event.pk, owner_member=ctx.actor, purpose="reimbursement_receipt",
        binding_kind="claim").first()
    require(row is not None, "not_found", status=404)
    _locked_claim(ctx, row.binding_uuid)
    return row


def create_claim_upload(*, request, event_id, claim_uuid, data):
    with command(event_id=event_id, actor=request.user, data=data, action=f"receipt.create:{claim_uuid}",
                 owner=True, request=request) as ctx:
        if ctx.replay:
            row = FinanceAttachment.objects.get(pk=ctx.replay["id"])
        else:
            claim = _locked_claim(ctx, claim_uuid)
            row = attachment_uploads.create_locked(makerspace=ctx.event.makerspace, event_id=ctx.event.pk,
                event_title=ctx.event.title, owner=ctx.actor, actor=ctx.actor, binding_kind="claim",
                binding_uuid=claim.uuid, data={key: data[key] for key in ("question_id", "filename", "bytes", "mime")})
            ctx.finish(row, asset_id=row.pk)
    if row.state == "initiated":
        return attachment_uploads.presign(row)
    return {"asset_id": row.pk, "generation": row.generation, "state": row.state, "upload": None}


def complete_claim_upload(*, request, event_id, asset_id, data):
    with command(event_id=event_id, actor=request.user, data=data, action=f"receipt.complete:{asset_id}",
                 owner=True, request=request) as ctx:
        if ctx.replay:
            return ctx.replay
        row = _locked_asset(ctx, asset_id)
        ctx.cas(row)
        attachment_processing.complete_locked(row, generation=data["generation"], actor=ctx.actor)
        return ctx.finish(row, asset_id=row.pk, generation=row.generation,
            status_url=f"/api/v1/member/makerspaces/{ctx.event.makerspace_id}/events/{ctx.event.pk}"
                       f"/reimbursement/receipt-files/{row.pk}/")


def delete_claim_upload(*, request, event_id, asset_id, data):
    with command(event_id=event_id, actor=request.user, data=data, action=f"receipt.delete:{asset_id}",
                 owner=True, request=request) as ctx:
        row = _locked_asset(ctx, asset_id)
        if ctx.replay:
            return metadata(row)
        ctx.cas(row)
        attachment_workflow.discard_locked(row, actor=ctx.actor)
        ctx.finish(row, asset_id=row.pk)
        return metadata(row)
