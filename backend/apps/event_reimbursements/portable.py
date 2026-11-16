"""Typed portable transforms preserve money and never resume operational work."""
from copy import deepcopy
import json

DROP_MODELS = frozenset({"event_reimbursements.ReimbursementWorkItem"})
MODEL_NAMES = frozenset({"ReimbursementProgramme", "ReimbursementBudgetPool", "BudgetEntry", "BudgetReservation",
    "GrantRequest", "GrantAward", "GrantAwardRevision", "ReimbursementClaim", "ClaimRevision", "ClaimLine",
    "ClaimDecision", "ClaimLineDecision", "ClaimAppeal", "ClaimScreeningReview", "ClaimAttendanceAttestation"})
PII_FIELDS = {
    "GrantRequest": ("origin", "destination", "need_statement", "itinerary", "estimated_cost", "reason", "eligibility_snapshot"),
    "GrantAward": ("note",), "ReimbursementClaim": ("draft_payload", "extension_reason"),
    "ClaimLine": ("vendor", "description", "traveller", "source_note", "route"),
    "ClaimDecision": ("reason",), "ClaimLineDecision": ("reason",), "ClaimAppeal": ("statement",),
    "ClaimScreeningReview": ("note",), "ClaimAttendanceAttestation": ("note",),
}
# Structural references inside encrypted structured text are remapped after source
# decrypt and before target encrypt, exclusively in the custodial memory pipeline.
JSON_REFERENCES = {
    "ClaimAttendanceAttestation.venue_evidence_refs": "opaque evidence labels; preserve, no inferred PKs",
    "ReimbursementClaim.draft_payload.lines[].receipt.asset_id": "payments.FinanceAttachment",
    "GrantRequest.estimated_cost.form.form_id": "reimbursement-request-{programme_id}",
    "GrantRequest.estimated_cost.snapshot.form_id": "reimbursement-request-{programme_id}",
    "GrantRequest.eligibility_snapshot.cohort": "events.HackathonApplicationCohort, decimal-string ID",
    "ReimbursementProgramme.eligible_cohorts[]": "events.HackathonApplicationCohort, decimal-string ID",
}


def transform(*, label, fields, map_reference, fidelity, transform_pii, target_now):
    if label in DROP_MODELS:
        return None
    if not label.startswith("event_reimbursements.") or fidelity not in ("full", "redacted"):
        raise ValueError("invalid_reimbursement_projection")
    name = label.split(".", 1)[1]
    if name not in MODEL_NAMES:
        raise ValueError("unknown_reimbursement_model")
    value = deepcopy(fields)
    if name == "ReimbursementProgramme":
        value.update(enabled=False, imported_paused=True, request_opens_at=None, request_closes_at=target_now)
        if "eligible_cohorts" in value:
            value["eligible_cohorts"] = [str(map_reference("events.HackathonApplicationCohort", int(item)))
                for item in value["eligible_cohorts"]]
    for key in PII_FIELDS.get(name, ()):
        if key not in value:
            continue
        if fidelity == "redacted":
            value[key] = "{}" if key in ("itinerary", "estimated_cost", "eligibility_snapshot", "draft_payload", "route") else ""
        else:
            # Custody callback takes plaintext only in memory and returns a target
            # envelope. No disk/diagnostics/export serialization is permitted here.
            def remap(plaintext, field=key):
                return remap_structured(name, field, plaintext, map_reference)
            value[key] = transform_pii(label=label, field=key, source_value=value[key], remap=remap)
    if name == "ClaimDecision":
        for key, target in (("attendance_checkin_event_id", "events.EventCheckInEvent"),
                            ("core_obligation_id", "payments.EventPayoutObligation"),
                            ("project_snapshot_ref", "reimbursement.project_evidence")):
            if value.get(key) is not None:
                value[key] = map_reference(target, value[key])
    if name == "ClaimAppeal" and value.get("resolved_by_cancellation_revision_id") is not None:
        value["resolved_by_cancellation_revision_id"] = map_reference("payments.EventPayoutObligationRevision",
            value["resolved_by_cancellation_revision_id"])
    # Preserve all budget amounts/reservations and accepted award snapshots. A
    # disabled programme requires explicit finance reconciliation before reuse.
    return value


def remap_structured(name, field, plaintext, map_reference):
    if (name, field) not in (("ReimbursementClaim", "draft_payload"), ("GrantRequest", "estimated_cost"),
                            ("GrantRequest", "eligibility_snapshot")):
        return plaintext
    value = json.loads(plaintext)
    if name == "ReimbursementClaim":
        for line in value.get("lines", []):
            receipt = line.get("receipt")
            if receipt:
                receipt["asset_id"] = map_reference("payments.FinanceAttachment", receipt["asset_id"])
    elif field == "eligibility_snapshot":
        if value.get("cohort"):
            value["cohort"] = str(map_reference("events.HackathonApplicationCohort", int(value["cohort"])))
    else:
        for obj in (value.get("form", {}), value.get("snapshot", {})):
            form_id = obj.get("form_id", "")
            if form_id.startswith("reimbursement-request-"):
                original = int(form_id.removeprefix("reimbursement-request-"))
                obj["form_id"] = "reimbursement-request-" + str(map_reference("event_reimbursements.ReimbursementProgramme", original))
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
