"""Trusted same-host hashes and versioned allocation snapshots."""
from collections import defaultdict
from apps.payments.event_payouts.attachment_models import FinanceAttachment
from apps.payments.event_payouts.receipt_models import ReceiptUse, ReceiptAllocation
from apps.payments.event_payouts.errors import require


def pin_receipts_locked(*, claim, lines, predeclared):
    by_hash = defaultdict(list)
    assets = {}
    for line in sorted(lines, key=lambda item: (item["receipt"]["asset_id"], str(item["line_uuid"]))):
        ref = line["receipt"]
        require(predeclared.get(ref["asset_id"]) == (ref["generation"], ref["sha256"]), "receipt_set_changed")
        asset = FinanceAttachment.objects.select_for_update().filter(pk=ref["asset_id"],
            makerspace_id=claim.event.makerspace_id, owner_member_id=claim.member_id,
            event_id_snapshot=claim.event_id, binding_kind="claim", binding_uuid=claim.uuid,
            purpose="reimbursement_receipt", generation=ref["generation"], sha256=ref["sha256"],
            state__in=("ready", "attached"), scan_status__in=("clean", "skipped")).first()
        require(asset is not None, "receipt_unavailable", status=404)
        require(asset.actual_bytes == asset.expected_bytes and asset.actual_bytes is not None and
            asset.actual_bytes > 0 and bool(asset.canonical_mime), "receipt_unavailable", status=404)
        assets[line["line_uuid"]] = asset
        by_hash[asset.sha256].append(line)
    uses = {}
    for digest, members in sorted(by_hash.items()):
        currency = members[0]["original_currency"]
        declared = members[0]["receipt"]["receipt_total_minor"]
        require(all(row["original_currency"] == currency and row["receipt"]["receipt_total_minor"] == declared
                    for row in members), "receipt_total_mismatch", status=400)
        require(sum(row["original_amount_minor"] for row in members) <= declared, "receipt_overallocated")
        use, created = ReceiptUse.objects.get_or_create(makerspace_id=claim.event.makerspace_id, sha256=digest,
            defaults={"original_currency": currency, "declared_total_minor": declared})
        use = ReceiptUse.objects.select_for_update().get(pk=use.pk)
        require(use.original_currency == currency and use.declared_total_minor == declared, "receipt_total_mismatch")
        current = list(use.allocations.filter(use_version=use.version))
        others = [row for row in current if row.claim_uuid != claim.uuid]
        # Splitting a receipt across claims needs the separate immutable finance
        # override. No hash existence or other-owner detail enters this error.
        authorized = use.overrides.filter(use_version=use.version).first()
        require(not others or authorized is not None, "receipt_duplicate")
        if authorized:
            expected = {(str(row["claim_uuid"]), str(row["line_uuid"]), row["original_amount_minor"])
                        for row in authorized.allocation_snapshot["allocations"]}
            require(all((str(claim.uuid), str(row["line_uuid"]), row["original_amount_minor"]) in expected
                        for row in members), "receipt_duplicate")
        else:
            if not created:
                use.version += 1
                use.save(update_fields=["version"])
            for row in members:
                ReceiptAllocation.objects.create(receipt_use=use, use_version=use.version,
                    claim_uuid=claim.uuid, line_uuid=row["line_uuid"], amount_minor=row["original_amount_minor"])
        uses[digest] = use
    return assets, uses
