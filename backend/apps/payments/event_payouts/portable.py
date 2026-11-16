"""Explicit custodial transforms; generic/account exports have no finance payload."""
from copy import deepcopy
from .decision_snapshots import validate_summary
from .wire import fingerprint

EPHEMERAL_MODELS = frozenset(("payments.EventPayoutCommandReceipt", "payments.PayoutExportBatch",
    "payments.PayoutExportBatchItem", "payments.FinanceSweepCursor", "payments.FinanceObjectCleanup"))
SUMMARY_REFERENCES = {
    "decision.actor_id": "accounts.User",
    "eligibility.registration_id": "events.EventRegistration",
    "eligibility.checkin_event_id": "events.EventCheckInEvent",
    "eligibility.correction_watermark": "events.EventCheckInEvent",
    "lines[].receipt.attachment_id": "payments.FinanceAttachment",
    "lines[].receipt.receipt_use_id": "payments.ReceiptUse",
}
UUID_FIELDS = {
    "payments.EventPayoutObligation": {"source_uuid": "event_reimbursements.ReimbursementClaim.uuid"},
    "payments.EventPayoutObligationRevision": {"decision_uuid": "event_reimbursements.ClaimDecision.uuid"},
    "payments.ReceiptAllocation": {"claim_uuid": "event_reimbursements.ReimbursementClaim.uuid",
                                    "line_uuid": "event_reimbursements.ClaimLine.line_uuid"},
}


def remap_core_references(model_label, values, *, map_uuid):
    """Non-FK typed fields only; G's ordinary FK/PK maps run separately."""
    result = deepcopy(values)
    if model_label == "payments.FinanceAttachment":
        kind = result["binding_kind"]
        if kind not in ("claim", "payee"):
            raise ValueError("Invalid finance binding.")
        label = "event_reimbursements.ReimbursementClaim.uuid" if kind == "claim" else "payments.EventPayeeRevision.id"
        result["binding_uuid"] = str(map_uuid(label, result["binding_uuid"]))
    elif model_label in UUID_FIELDS:
        for field, label in UUID_FIELDS[model_label].items():
            if result.get(field) is not None:
                result[field] = str(map_uuid(label, result[field]))
    else:
        raise ValueError("Undeclared finance reference model.")
    return result


def remap_eligibility(value, *, map_id, map_uuid):
    from .decision_snapshots import eligibility
    from .preflight import Facts
    result = deepcopy(value)
    wrapped = isinstance(result, dict) and "evidence" in result
    if wrapped:
        Facts.from_dict(result)
    evidence = result["evidence"] if wrapped else result
    eligibility(evidence)
    for key, label in (("registration_id", "events.EventRegistration"), ("checkin_event_id", "events.EventCheckInEvent"),
                       ("correction_watermark", "events.EventCheckInEvent")):
        # The importer explicitly returns an inert original when its domain row
        # was purged and does not travel; no resolver ever guesses by ID/email.
        if evidence[key] is not None and evidence[key] != 0:
            evidence[key] = map_id(label, evidence[key])
    for key, label in (("attestation_uuid", "event_reimbursements.ClaimAttendanceAttestation.uuid"),
                       ("project_snapshot_ref", "events.project_snapshot_ref")):
        if evidence[key] is not None:
            evidence[key] = str(map_uuid(label, evidence[key]))
    eligibility(evidence)
    return result


def remap_allocations(value, *, map_uuid):
    from .validation import closed, minor
    result = deepcopy(value)
    if not isinstance(result, list):
        raise ValueError("Invalid receipt allocations.")
    for item in result:
        closed(item, ("claim_uuid", "line_uuid", "original_amount_minor"))
        minor(item["original_amount_minor"])
        item["claim_uuid"] = str(map_uuid("event_reimbursements.ReimbursementClaim.uuid", item["claim_uuid"]))
        item["line_uuid"] = str(map_uuid("event_reimbursements.ClaimLine.line_uuid", item["line_uuid"]))
    return result


def remap_hold_refs(value, *, map_id):
    from .validation import minor
    if not isinstance(value, list) or len(value) > 100:
        raise ValueError("Invalid hold evidence references.")
    return [map_id("payments.PayoutEligibility", minor(identifier)) for identifier in value]


def remap_summary(snapshot, *, map_id, map_uuid, fidelity="full"):
    result = validate_summary(snapshot)
    if fidelity not in ("full", "redacted"):
        raise ValueError("Unsupported finance fidelity.")
    decision = result["decision"]
    if decision["actor_id"] is not None:
        decision["actor_id"] = map_id("accounts.User", decision["actor_id"])
    result["eligibility"] = remap_eligibility(result["eligibility"], map_id=map_id, map_uuid=map_uuid)
    for key, label in (("claim_uuid", "event_reimbursements.ReimbursementClaim.uuid"),
                       ("decision_uuid", "event_reimbursements.ClaimDecision.uuid")):
        result["source"][key] = str(map_uuid(label, result["source"][key]))
    result["award"]["uuid"] = str(map_uuid("event_reimbursements.GrantAward.uuid", result["award"]["uuid"]))
    if fidelity == "redacted":
        decision["reason"] = "[redacted]"
    for line in result["lines"]:
        line["line_uuid"] = str(map_uuid("event_reimbursements.ClaimLine.line_uuid", line["line_uuid"]))
        receipt = line["receipt"]
        receipt["attachment_id"] = map_id("payments.FinanceAttachment", receipt["attachment_id"])
        receipt["receipt_use_id"] = map_id("payments.ReceiptUse", receipt["receipt_use_id"])
        if receipt["override_uuid"]:
            receipt["override_uuid"] = str(map_uuid("payments.ReceiptAllocationOverride.id", receipt["override_uuid"]))
            receipt["override_allocation"] = remap_allocations(receipt["override_allocation"], map_uuid=map_uuid)
        if fidelity == "redacted":
            for key in ("vendor", "description", "traveller", "source_note", "reason"):
                line[key] = "[redacted]"
            if receipt["override_uuid"]:
                receipt["override_reason"] = "[redacted]"
    # Closed G1 v1 has no extra redaction-marker property: use the redacted text
    # marker in the existing identifying fields, preserving its exact schema.
    return validate_summary(result)


def import_obligation(values, *, domain_included, source_closure_proven):
    result = deepcopy(values)
    if (type(domain_included) is not bool or type(source_closure_proven) is not bool
            or result["domain_coordination_state"] not in ("attached", "detached")):
        raise ValueError("Invalid finance coordination projection.")
    if domain_included and result["domain_coordination_state"] == "attached":
        if not source_closure_proven:
            raise ValueError("Attached finance requires its full typed domain closure.")
    else:
        result.update(domain_coordination_state="detached", event_id=None)
    # Target admission never treats a source acknowledgement as live authority.
    result["eligibility_status"] = "needs_acknowledgement" if result["state"] == "open" else result["eligibility_status"]
    return result


def import_payee(values, *, now, hold_active, liability_open):
    result = deepcopy(values)
    due = result.get("purge_due_at")
    if result.pop("_finance_redacted", False):
        result.update(details="", state="purged", purged_at=now)
    elif result.get("state") == "purged" or due is not None and due <= now and not hold_active and not liability_open:
        result.update(details="", state="purged", purged_at=result.get("purged_at") or now)
    return result


def import_attachment(values):
    if values["state"] not in ("ready", "attached", "expired", "deleting", "deleted"):
        # A target may not replay a source upload/validation operation. G drops
        # these coordination rows and explicitly reconciles any draft references.
        return None
    result = deepcopy(values)
    result.update(lease_token=None, lease_until=None, attempts=0, staging_version_id="")
    # Canonical final keys/versions are populated by the object-journal provider;
    # never reuse a source presign/staging locator or restart an upload abroad.
    return result


def money_fingerprint(obligations, entries):
    def select(row, fields):
        return {key: row[key] for key in fields}
    debts = [select(row, ("id", "currency", "approved_minor", "state", "current_revision_id")) for row in obligations]
    ledger = [select(row, ("id", "obligation_id", "currency", "amount_minor", "amends_id", "is_void")) for row in entries]
    return fingerprint({"obligations": sorted(debts, key=lambda row: str(row["id"])),
                        "entries": sorted(ledger, key=lambda row: str(row["id"]))})
