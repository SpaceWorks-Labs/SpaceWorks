"""Presentation entries: release-2 lane L16 (technicians, issue reports, repairs, item/room maintenance).

``permitted`` lists only reviewed non-personal leaf paths (ids, counts, states, channels);
remarks, reasons and a reporter's or technician's details stay in the raw audit row."""

from .presentation_catalog_types import P

_I = ("issue_id", "area", "state")

ENTRIES = (
    P("issue.reported", "Problem reported", (*_I, "source", "subject_type", "photos")),
    P("issue.opened", "Repair job opened", (*_I, "subject_type", "work_order_id")),
    P("issue.triaged", "Issue triaged", (*_I, "work_order_id", "priority")),
    P("issue.rejected", "Issue rejected", _I),
    P("issue.assigned", "Issue assigned", (*_I, "assignment_id", "self_assigned", "contact_id")),
    P("issue.unassigned", "Assignee removed", (*_I, "assignment_id")),
    P("issue.dispatched", "Issue sent to technicians", ("issue_id", "contacts", "sends", "failed")),
    P("issue.closed", "Issue closed", _I),
    P("dispatch.sent", "Sent to a technician", (*_I, "contact_id", "channels", "delivered")),
    P("repair.started", "Repair started", _I),
    P("repair.fixed", "Repair fixed", (*_I, "photos", "reporter_notified")),
    P("repair.visit_logged", "Technician visit logged", (*_I, "photos")),
    P("repair.remark_logged", "Repair remark added", (*_I, "photos")),
    P("repair.parts_used", "Parts used on a repair", (*_I, "part_id", "product_id", "quantity", "to_buy_item_id")),
    P("repair.parts_needed", "Parts needed for a repair", (*_I, "part_id", "product_id", "quantity",
                                                          "to_buy_item_id")),
    P("repair.quote_recorded", "Repair quote recorded", (*_I, "currency", "contact_id")),
    P("repair.quote_approved", "Repair quote approved", _I),
    P("repair.quote_declined", "Repair quote declined", _I),
    P("repair.payout_recorded", "Repair payout recorded", (*_I, "ledger_entry_id", "domain", "machine_type_id",
                                                          "method")),
    P("service_state.changed", "Service state changed", ("issue_id", "area", "state", "subject_type", "machine_id",
                                                        "product_id", "asset_id", "room_id", "in_service",
                                                        "affected_bookings", "outage_id")),
    P("technician.created", "Technician added", ("contact_id", "kind")),
    P("technician.updated", "Technician changed", ("contact_id", "fields")),
    P("technician.archived", "Technician archived", ("contact_id",)),
    P("technician.opt_in_link_created", "Technician opt-in link sent", ("contact_id", "emailed")),
    P("technician.opted_in", "Technician opted in to chat", ("contact_id", "channels")),
    P("technician.consent_withdrawn", "Technician chat consent withdrawn", ("contact_id", "channel")),
    P("technician.default_set", "Default technician set", ("contact_id", "area", "machine_type_id", "room_id")),
    P("technician.default_removed", "Default technician removed", ("contact_id", "area", "machine_type_id",
                                                                  "room_id")),
    P("maintenance.subject_schedule_created", "Item or room maintenance scheduled",
      ("schedule_id", "subject_type", "product_id", "asset_id", "room_id")),
    P("maintenance.subject_schedule_updated", "Item or room maintenance schedule changed", ("schedule_id", "fields")),
    P("maintenance.subject_logged", "Item or room maintenance logged", ("log_id", "schedule_id", "subject_type")),
)
