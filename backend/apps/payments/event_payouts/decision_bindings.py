"""Validate permanent receipt references under the caller's ordered parent locks."""
from uuid import UUID
from django.db.models import Q
from .attachment_models import FinanceAttachment
from .receipt_models import ReceiptUse, ReceiptAllocation, ReceiptAllocationOverride
from .errors import require


def validate_locked(*, snapshot, obligation):
    lines = snapshot["lines"]
    assets = {r.pk: r for r in FinanceAttachment.objects.select_for_update().filter(
        Q(pk__in={line["receipt"]["attachment_id"] for line in lines})
        | Q(makerspace_id=obligation.makerspace_id, binding_kind="claim", binding_uuid=obligation.source_uuid)).order_by("pk")}
    uses = {r.pk: r for r in ReceiptUse.objects.select_for_update().filter(
        pk__in={line["receipt"]["receipt_use_id"] for line in lines}).order_by("pk")}
    for line in lines:
        receipt = line["receipt"]
        asset, use = assets.get(receipt["attachment_id"]), uses.get(receipt["receipt_use_id"])
        require(asset is not None and use is not None, "decision_receipt_missing")
        require(asset.makerspace_id == use.makerspace_id == obligation.makerspace_id
            and asset.owner_member_id == obligation.owner_member_id
            and asset.event_id_snapshot == obligation.event_id_snapshot
            and asset.binding_kind == "claim" and asset.binding_uuid == obligation.source_uuid
            and asset.purpose == "reimbursement_receipt" and asset.obligation_id in (None, obligation.pk),
            "decision_receipt_scope_mismatch")
        require(asset.generation == receipt["generation"] and asset.sha256 == use.sha256 == receipt["sha256"]
            and asset.state == "attached" and asset.scan_status in ("clean", "skipped")
            and asset.actual_bytes == asset.expected_bytes and asset.canonical_mime, "decision_receipt_unavailable")
        require(use.original_currency == receipt["currency"] and use.declared_total_minor == receipt["total_minor"]
            and receipt["receipt_use_version"] <= use.version, "decision_receipt_changed")
        allocation = ReceiptAllocation.objects.filter(receipt_use=use, use_version=receipt["receipt_use_version"],
            claim_uuid=obligation.source_uuid, line_uuid=UUID(line["line_uuid"])).first()
        require(allocation is not None and allocation.amount_minor == receipt["allocation_minor"]
            and allocation.override_id == (UUID(receipt["override_uuid"]) if receipt["override_uuid"] else None),
            "decision_allocation_changed")
        if receipt["override_uuid"]:
            override = ReceiptAllocationOverride.objects.filter(pk=receipt["override_uuid"], receipt_use=use,
                use_version=receipt["receipt_use_version"]).first()
            require(override is not None and override.allocation_snapshot == receipt["override_allocation"]
                and override.reason_code == receipt["override_reason_code"] and override.note == receipt["override_reason"]
                and override.total_minor == receipt["total_minor"] and override.currency == receipt["currency"],
                "decision_override_changed")
