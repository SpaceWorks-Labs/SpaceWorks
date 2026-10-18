"""Masked, expiring reconciliation checklists. There is no transfer instruction."""
from datetime import timedelta
from uuid import uuid4
from django.db import transaction
from django.utils import timezone
from apps.audit.services import record
from apps.encryption.account_write_fence import account_fences
from apps.encryption.tenant_preparation import prepare_tenant_key, tenant_key_context
from apps.makerspaces.models import Makerspace
from apps.tenant_migration.gate_runtime import boundary_tenant_write, assert_write_allowed
from .authority import authorize
from .errors import require
from .export_models import PayoutExportBatch, PayoutExportBatchItem
from .obligation_models import EventPayoutObligation
from .payee_workflow import current, projection
from .queries import paid
from .transactions import fingerprint, lock_finance_authority
from .csv_values import encode_rows


def ready(obligation, payee):
    require(obligation.state == "open" and obligation.eligibility_status == "eligible"
            and not obligation.hold_reason_code, "export_selection_held")
    require(payee is not None and payee.state == "current" and payee.verified_at and payee.details,
            "payee_not_ready")
    require(paid(obligation) < obligation.approved_minor, "export_selection_settled")


def create(*, request, makerspace_id, data):
    space = Makerspace.objects.get(pk=makerspace_id)
    authorize(request, space, mutation=True)
    assert_write_allowed(space.pk)
    ids = data["obligation_ids"]
    require(len(ids) == len(set(ids)) and 0 < len(ids) <= 500, "invalid_export_selection", status=400)
    seed = list(EventPayoutObligation.objects.filter(pk__in=ids, makerspace=space).order_by("pk"))
    require(len(seed) == len(ids), "not_found", status=404)
    accounts = tuple(sorted({request.user.pk, *(row.owner_member_id for row in seed if row.owner_member_id)}))
    digest = fingerprint({"action": "export.create", "makerspace_id": space.pk, "data": data})
    key = prepare_tenant_key(space.pk)
    with boundary_tenant_write(space.pk), tenant_key_context(key), transaction.atomic(), account_fences(accounts, (space.pk,)):
        space = Makerspace.objects.select_for_update().get(pk=space.pk)
        request.user = lock_finance_authority(request.user, space)
        authorize(request, space, mutation=True)
        prior = PayoutExportBatch.objects.filter(operation_id=data["operation_id"]).first()
        if prior:
            require(prior.makerspace_id == space.pk and prior.created_by_id == request.user.pk
                    and prior.command_digest == digest, "idempotency_conflict")
            return {"id": str(prior.pk), "expires_at": prior.expires_at.isoformat()}
        require(data["expected_version"] == 0, "stale_version")
        rows = list(EventPayoutObligation.objects.select_for_update().filter(pk__in=ids, makerspace=space).order_by("pk"))
        require([(row.pk, row.owner_member_id) for row in rows] == [(row.pk, row.owner_member_id) for row in seed], "scope_changed")
        batch = PayoutExportBatch.objects.create(makerspace=space, created_by=request.user,
            operation_id=data["operation_id"], command_digest=digest, selection_filter={"obligation_ids": sorted(map(str, ids))},
            selection_hash=fingerprint(sorted(map(str, ids))), expires_at=timezone.now() + timedelta(hours=24))
        preview = []
        for row in rows:
            payee = current(row, lock=True)
            ready(row, payee)
            remaining = row.approved_minor - paid(row)
            PayoutExportBatchItem.objects.create(batch=batch, obligation=row, obligation_version=row.version,
                payee_revision=payee, payee_version=payee.version, remaining_minor=remaining)
            preview.append({"obligation_id": str(row.pk), "currency": row.currency,
                            "remaining_minor": remaining, "masked_payee": projection(payee)["masked_details"]})
        record(request.user, "finance.event_payout.export_created", makerspace=space, target=batch,
               meta={"batch_id": str(batch.pk), "count": len(rows), "mask_policy_version": 1})
        return {"id": str(batch.pk), "expires_at": batch.expires_at.isoformat(), "preview": preview}


def download(*, request, makerspace_id, batch_id):
    space = Makerspace.objects.get(pk=makerspace_id)
    authorize(request, space)
    assert_write_allowed(space.pk)
    batch = PayoutExportBatch.objects.get(pk=batch_id, makerspace=space)
    key = prepare_tenant_key(space.pk, create=False)
    with boundary_tenant_write(space.pk), tenant_key_context(key), transaction.atomic(), account_fences((request.user.pk,), (space.pk,)):
        space = Makerspace.objects.select_for_update().get(pk=space.pk)
        request.user = lock_finance_authority(request.user, space)
        authorize(request, space)
        now = timezone.now()
        require(batch.state == "ready" and now < batch.expires_at, "export_expired", status=410)
        items = list(batch.items.select_related("obligation__current_revision", "payee_revision").order_by("obligation_id"))
        rows = []
        for item in items:
            row = EventPayoutObligation.objects.select_for_update().get(pk=item.obligation_id)
            payee = current(row, lock=True)
            ready(row, payee)
            require(row.version == item.obligation_version and payee.pk == item.payee_revision_id
                    and payee.version == item.payee_version and row.approved_minor - paid(row) == item.remaining_minor,
                    "export_selection_changed")
            rows.append({"batch_id": str(batch.pk), "obligation_id": str(row.pk), "event_id": str(row.event_id_snapshot),
                "event_title": row.event_title_snapshot, "participant_reference": str(row.owner_member_id or "retained"),
                "country": payee.country, "method": payee.method, "masked_payee": projection(payee)["masked_details"],
                "currency": row.currency, "approved_minor": row.approved_minor, "effective_paid_minor": paid(row),
                "remaining_minor": item.remaining_minor, "payee_revision": str(payee.pk), "claim_reference": str(row.source_uuid),
                "decision_reference": str(row.current_revision_id), "exported_at": now.isoformat()})
        batch.download_count += 1
        batch.downloaded_at = now
        batch.save(update_fields=["download_count", "downloaded_at"])
        record(request.user, "finance.event_payout.export_downloaded", makerspace=space, target=batch,
               meta={"batch_id": str(batch.pk), "count": len(rows), "mask_policy_version": 1})
        return encode_rows(rows)
