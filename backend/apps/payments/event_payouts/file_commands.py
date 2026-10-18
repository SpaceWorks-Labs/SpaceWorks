"""Owner payee upload commands; R uses the same locked port for claim receipts."""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.audit.services import record
from .attachment_models import FinanceAttachment
from . import attachment_workflow as workflow
from .errors import require
from .transactions import command


def status(row):
    return {"asset_id": row.pk, "generation": row.generation, "version": row.version, "state": row.state,
        "filename": row.original_filename, "bytes": row.expected_bytes, "sha256": row.sha256,
        "scan_status": row.scan_status, "error_code": row.error_code}


def payee_asset(obligation, asset_id, *, lock=False):
    rows = FinanceAttachment.objects
    if lock:
        rows = rows.select_for_update()
    return get_object_or_404(rows, pk=asset_id, obligation=obligation, owner_member_id=obligation.owner_member_id,
        binding_kind="payee", purpose="reimbursement_payee_document")


def create(*, request, obligation_id, data):
    with command(request=request, obligation_id=obligation_id, data=data, action="payee.file.create", owner=True) as ctx:
        if ctx.replay:
            row = payee_asset(ctx.obligation, ctx.replay["asset_id"])
        else:
            ctx.cas()
            payee = ctx.obligation.payee_revisions.select_for_update().filter(pk=data["payee_revision_id"], state="current").first()
            require(payee is not None and payee.version == data["expected_payee_version"] and not payee.verified_at,
                    "stale_payee_version")
            row = workflow.create_locked(makerspace=ctx.obligation.makerspace, event_id=ctx.obligation.event_id_snapshot,
                event_title=ctx.obligation.event_title_snapshot, owner=ctx.actor, actor=ctx.actor,
                binding_kind="payee", binding_uuid=payee.pk, obligation=ctx.obligation,
                data={key: data[key] for key in ("question_id", "filename", "bytes", "mime")})
            ctx.obligation.version += 1
            ctx.obligation.save(update_fields=["version"])
            ctx.finish(asset_id=row.pk)
    # Each replay gets a fresh authorized staging presign only while initiated.
    return workflow.presign(row) if row.state == "initiated" else {"asset_id": row.pk, "generation": row.generation, "state": row.state}


def mutate(*, request, obligation_id, asset_id, data, complete=False):
    action = f"payee.file.{'complete' if complete else 'discard'}:{asset_id}"
    with command(request=request, obligation_id=obligation_id, data=data, action=action, owner=True) as ctx:
        if ctx.replay:
            return ctx.replay
        ctx.cas()
        list(ctx.obligation.payee_revisions.select_for_update().order_by("pk"))
        row = payee_asset(ctx.obligation, asset_id, lock=True)
        require(row.version == data["expected_asset_version"] and row.generation == data["generation"], "attachment_changed")
        require(ctx.obligation.state == "open", "payee_not_requested")
        if complete:
            workflow.complete_locked(row, generation=data["generation"], actor=ctx.actor)
        else:
            workflow.discard_locked(row, actor=ctx.actor)
        ctx.obligation.version += 1
        ctx.obligation.save(update_fields=["version"])
        return ctx.finish(asset_id=row.pk, generation=row.generation, state=row.state,
            status_url=f"/api/v1/member/event-payouts/{ctx.obligation.pk}/payee-files/{row.pk}/")
