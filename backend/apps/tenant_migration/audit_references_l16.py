"""Audit metadata IDs written by release-2 lane L16 (technicians, issues, repairs, maintenance)."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP

_ISSUE_ACTIONS = (
    "issue.reported", "issue.opened", "issue.triaged", "issue.rejected", "issue.assigned", "issue.unassigned",
    "issue.dispatched", "issue.closed", "dispatch.sent", "repair.started", "repair.fixed", "repair.visit_logged",
    "repair.remark_logged", "repair.parts_used", "repair.parts_needed", "repair.quote_recorded",
    "repair.quote_approved", "repair.quote_declined", "repair.payout_recorded", "service_state.changed",
    "repair.loan_handoff",
)
_CONTACT_ACTIONS = (
    "issue.assigned", "dispatch.sent", "repair.quote_recorded", "technician.created", "technician.updated",
    "technician.archived", "technician.opt_in_link_created", "technician.opted_in", "technician.consent_withdrawn",
    "technician.default_set", "technician.default_removed",
)


def _remap(model, *edges):
    return {edge: AuditReference(R, model) for edge in edges}


EDGES = {
    **_remap("maintenance.IssueReport", *((action, "issue_id") for action in _ISSUE_ACTIONS),
             ("procurement.item_added", "issue_id")),
    **_remap("maintenance.TechnicianContact", *((action, "contact_id") for action in _CONTACT_ACTIONS)),
    **_remap("maintenance.WorkOrder", ("issue.opened", "work_order_id"), ("issue.triaged", "work_order_id"),
             ("repair.loan_handoff", "work_order_id")),
    **_remap("hardware_requests.HardwareRequest", ("repair.loan_handoff", "request_id")),
    **_remap("hardware_requests.RequesterAccountability", ("repair.loan_handoff", "accountability_id")),
    **_remap("evidence.EvidencePhoto", ("repair.loan_handoff", "evidence_id")),
    **_remap("maintenance.IssueAssignment", ("issue.assigned", "assignment_id"), ("issue.unassigned", "assignment_id")),
    **_remap("maintenance.RepairPart", ("repair.parts_used", "part_id"), ("repair.parts_needed", "part_id")),
    **_remap("inventory.InventoryProduct", ("repair.parts_used", "product_id"), ("repair.parts_needed", "product_id"),
             ("service_state.changed", "product_id"), ("maintenance.subject_schedule_created", "product_id")),
    **_remap("procurement.ToBuyItem", ("repair.parts_used", "to_buy_item_id"),
             ("repair.parts_needed", "to_buy_item_id")),
    **_remap("payments.LedgerEntry", ("repair.payout_recorded", "ledger_entry_id")),
    **_remap("machines.MachineType", ("repair.payout_recorded", "machine_type_id"),
             ("technician.default_set", "machine_type_id"), ("technician.default_removed", "machine_type_id")),
    **_remap("bookings.BookableSpace", ("technician.default_set", "room_id"),
             ("technician.default_removed", "room_id"), ("service_state.changed", "room_id"),
             ("maintenance.subject_schedule_created", "room_id")),
    **_remap("machines.Machine", ("service_state.changed", "machine_id")),
    **_remap("inventory.InventoryAsset", ("service_state.changed", "asset_id"),
             ("maintenance.subject_schedule_created", "asset_id")),
    **_remap("maintenance.RoomOutage", ("service_state.changed", "outage_id")),
    **_remap("maintenance.SubjectMaintenanceSchedule", ("maintenance.subject_schedule_created", "schedule_id"),
             ("maintenance.subject_schedule_updated", "schedule_id"), ("maintenance.subject_logged", "schedule_id")),
    **_remap("maintenance.SubjectMaintenanceLog", ("maintenance.subject_logged", "log_id")),
}
