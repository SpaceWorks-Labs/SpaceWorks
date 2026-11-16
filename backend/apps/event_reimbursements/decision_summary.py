"""Build the G1 closed core-evidence shape from locked, trusted domain records."""
from datetime import timezone
from apps.payments.currencies import supported_minor_unit_exponent
from apps.payments.event_payouts.errors import require
from apps.payments.event_payouts.receipt_models import ReceiptUse


def utc(value):
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds" if value.microsecond else "seconds").replace("+00:00", "Z")


def build(*, claim, decision, line_decisions, attendance, eligibility_revision):
    award = claim.award
    lines = []
    for row in line_decisions:
        line, asset = row.line, row.line.finance_asset
        use = ReceiptUse.objects.get(makerspace_id=claim.event.makerspace_id, sha256=line.receipt_hash)
        allocation = use.allocations.filter(claim_uuid=claim.uuid, line_uuid=line.line_uuid,
            amount_minor=line.original_amount_minor).order_by("-use_version").first()
        require(allocation is not None, "receipt_allocation_missing")
        override = allocation.override
        lines.append({"line_uuid": str(line.line_uuid), "category": line.category,
            "expense_date": line.expense_date.isoformat(), "vendor": line.vendor, "description": line.description,
            "traveller": line.traveller, "original_amount_minor": line.original_amount_minor,
            "original_currency": line.original_currency, "original_exponent": supported_minor_unit_exponent(line.original_currency),
            "fx_rate": format(line.fx_rate, ".12f"), "rate_date": line.rate_date.isoformat(),
            "rate_source": line.rate_source, "source_note": line.source_note, "currency": award.currency,
            "target_exponent": supported_minor_unit_exponent(award.currency), "converted_minor": line.converted_minor,
            "approved_minor": row.approved_minor, "limits": {"cap_minor": award.calculation_snapshot.get(
                "category_caps", {}).get(line.category, award.amount_minor)}, "rounding": "HALF_UP",
            "reason_code": row.reason_code, "reason": row.reason, "receipt": {
                "attachment_id": asset.pk, "generation": asset.generation, "sha256": line.receipt_hash,
                "total_minor": use.declared_total_minor, "currency": use.original_currency,
                "receipt_use_id": use.pk, "receipt_use_version": allocation.use_version,
                "allocation_minor": allocation.amount_minor, "override_uuid": str(override.pk) if override else None,
                "override_allocation": override.allocation_snapshot["allocations"] if override else [],
                "override_reason_code": override.reason_code if override else "", "override_reason": override.note if override else ""}})
    return {"schema_version": 1, "source": {"claim_uuid": str(claim.uuid), "claim_revision": decision.revision.revision,
            "decision_uuid": str(decision.uuid), "decision_sequence": decision.sequence},
        "decision": {"outcome": decision.outcome, "decided_at": utc(decision.decided_at), "actor_id": decision.actor_id,
                     "reason_code": decision.reason_code, "reason": decision.reason},
        "award": {"uuid": str(award.uuid), "cap_minor": award.amount_minor, "currency": award.currency,
            "policy_revision": award.calculation_snapshot.get("policy_revision", award.rule_revision),
            # The frozen G1 shape carries only the per-category caps the decision applied.
            "rule_revision": award.rule_revision,
            "applied_rules": {"category_caps": dict(award.calculation_snapshot.get("category_caps", {}))}},
        "totals": {"claimed_minor": decision.revision.total_minor, "eligible_minor": sum(l.converted_minor for l in
            decision.revision.lines.all()), "approved_minor": decision.approved_total_minor}, "lines": lines,
        "eligibility": {"registration_id": attendance["registration_id"], "attendance_revision": attendance["attendance_revision"],
            "checkin_event_id": decision.attendance_checkin_event_id, "correction_watermark": attendance["invalidated_through_checkin_id"],
            "attestation_uuid": attendance["attestation_uuid"], "project_snapshot_ref": str(decision.project_snapshot_ref)
            if decision.project_snapshot_ref else None, "core_eligibility_revision": eligibility_revision}}
