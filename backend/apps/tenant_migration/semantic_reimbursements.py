"""Typed non-FK references of portable stage-form, reimbursement and payout rows.

Ordinary FKs are remapped by the importer. This module owns the rest: integer IDs held
in plain columns, UUID-valued references and typed slots inside plaintext JSON. The
reference shapes are the packages' own (``portable.py``); nothing here searches text.

Domain UUIDs (claim, award, line, decision and attestation ``uuid`` columns) are
preserved verbatim with a refuse-on-collision rule, so references to them by value stay
valid. References to UUID *primary keys* follow the importer's PK map.
"""
from contextvars import ContextVar
from uuid import NAMESPACE_URL, UUID, uuid5

from .insertion_errors import ArchiveFormatError

# Value labels the package transforms use for UUID primary keys.
UUID_PRIMARY_KEYS = {
    "payments.EventPayeeRevision.id": "payments.EventPayeeRevision",
    "payments.ReceiptAllocationOverride.id": "payments.ReceiptAllocationOverride",
}
_project_refs = ContextVar("reimbursement_project_refs", default=None)


def project_ref(event_id, snapshot_id):
    return uuid5(NAMESPACE_URL, f"spaceworks:submission-snapshot:{event_id}:{snapshot_id}")


def prepare_project_refs(archive, pk_map):
    """Map source project-evidence references to the target's equivalent identity."""
    from django.apps import apps
    submissions = {row["id"]: row["event_id"] for row in archive.rows("events.HackathonSubmission")}
    refs = {}
    Event, Snapshot = apps.get_model("events.Event"), apps.get_model("events.SubmissionSnapshot")
    for row in archive.rows("events.SubmissionSnapshot"):
        event_id = submissions.get(row["submission_id"])
        if event_id is None:
            continue
        refs[str(project_ref(event_id, row["id"]))] = str(project_ref(
            pk_map.lookup(Event, event_id), pk_map.lookup(Snapshot, row["id"])))
    return _project_refs.set(refs)


def reset_project_refs(token):
    _project_refs.reset(token)


def _map_project(value):
    refs = _project_refs.get() or {}
    try:
        return refs[str(value)]
    except KeyError as exc:
        raise ArchiveFormatError("Reimbursement project evidence names a snapshot the archive lacks.") from exc


def uuid_mapper(map_id):
    def map_uuid(label, value):
        if value is None:
            return None
        if label in UUID_PRIMARY_KEYS:
            return map_id(UUID_PRIMARY_KEYS[label], UUID(str(value)))
        if label in ("events.project_snapshot_ref", "reimbursement.project_evidence"):
            return _map_project(value)
        return value
    return map_uuid


def _int(map_id, label, value):
    return None if value is None else map_id(label, int(value))


def remap(label, source, row, map_id):
    """Rewrite one final row in place; never touches encrypted columns."""
    map_uuid = uuid_mapper(map_id)
    if label in ("events.EventStageForm", "events.StageFormAssignment"):
        from apps.events.staged_forms.portable import remap_json
        field = "audience" if label == "events.EventStageForm" else "policy_snapshot"
        row[field] = remap_json(f"{label}.{field}", row[field], map_id=map_id)
    elif label == "event_reimbursements.ReimbursementProgramme":
        row["eligible_cohorts"] = [str(map_id("events.HackathonApplicationCohort", int(item)))
                                   for item in row["eligible_cohorts"] or []]
    elif label == "event_reimbursements.ClaimDecision":
        row["attendance_checkin_event_id"] = _int(map_id, "events.EventCheckInEvent", row["attendance_checkin_event_id"])
        if row["core_obligation_id"] is not None:
            row["core_obligation_id"] = map_id("payments.EventPayoutObligation", UUID(str(row["core_obligation_id"])))
        row["project_snapshot_ref"] = map_uuid("events.project_snapshot_ref", row["project_snapshot_ref"])
    elif label == "event_reimbursements.ClaimAppeal":
        row["resolved_by_cancellation_revision_id"] = _int(
            map_id, "payments.EventPayoutObligationRevision", row["resolved_by_cancellation_revision_id"])
    elif label == "events.EventAttendanceCorrection":
        row["invalidated_through_checkin_id"] = _int(map_id, "events.EventCheckInEvent", row["invalidated_through_checkin_id"])
    elif label == "payments.EventPayoutObligation":
        from apps.payments.event_payouts.portable import import_obligation, remap_eligibility
        if row["eligibility_evidence"]:
            row["eligibility_evidence"] = remap_eligibility(row["eligibility_evidence"], map_id=map_id, map_uuid=map_uuid)
        if row["event_id_snapshot"] is not None and row["event_id"] is not None:
            row["event_id_snapshot"] = row["event_id"]
        row.update(import_obligation(row, domain_included=row["event_id"] is not None,
                                     source_closure_proven=row["event_id"] is not None))
    elif label == "payments.PayoutEligibility":
        from apps.payments.event_payouts.portable import remap_eligibility
        row["evidence"] = remap_eligibility(row["evidence"], map_id=map_id, map_uuid=map_uuid)
    elif label == "payments.PayoutHold":
        from apps.payments.event_payouts.portable import remap_hold_refs
        row["evidence_refs"] = remap_hold_refs(row["evidence_refs"] or [], map_id=map_id)
    elif label == "payments.FinanceAttachment":
        from apps.payments.event_payouts.portable import remap_core_references
        row["binding_uuid"] = remap_core_references(label, row, map_uuid=map_uuid)["binding_uuid"]
        if row["event_id_snapshot"] is not None and row["event_id"] is not None:
            row["event_id_snapshot"] = row["event_id"]
    elif label == "payments.ReceiptAllocationOverride":
        from apps.payments.event_payouts.portable import remap_allocations
        row["allocation_snapshot"] = remap_allocations(row["allocation_snapshot"], map_uuid=map_uuid)
    return True
