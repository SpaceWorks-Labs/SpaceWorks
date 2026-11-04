"""Presentation entries: release-2 lane L16 (technicians, issue reports, repairs, item/room maintenance).

``permitted`` lists only reviewed non-personal leaf paths (ids, counts, states, channels);
remarks, reasons and a reporter's or technician's details stay in the raw audit row.

Repair-timeline steps (``issue.reported`` ... ``repair.payout_recorded``) are written through
the ``maintenance/repairs/history.step`` wrapper and so have no entry here: the deny policy in
``presentation_l16_dynamic`` covers them. Actions with a branch-chosen name or runtime-built
metadata keep their label but permit no metadata."""

from .presentation_catalog_types import P

ENTRIES = (
    P("issue.dispatched", "Issue sent to technicians", ("issue_id", "contacts", "sends", "failed")),
    P("service_state.changed", "Service state changed", ()),
    P("technician.created", "Technician added", ("contact_id", "kind")),
    P("technician.updated", "Technician changed", ("contact_id", "fields")),
    P("technician.archived", "Technician archived", ("contact_id",)),
    P("technician.opt_in_link_created", "Technician opt-in link sent", ("contact_id", "emailed")),
    P("technician.opted_in", "Technician opted in to chat", ("contact_id", "channels")),
    P("technician.consent_withdrawn", "Technician chat consent withdrawn", ("contact_id", "channel")),
    P("technician.default_set", "Default technician set", ()),
    P("technician.default_removed", "Default technician removed", ()),
    P("maintenance.subject_schedule_created", "Item or room maintenance scheduled", ()),
    P("maintenance.subject_schedule_updated", "Item or room maintenance schedule changed", ("schedule_id", "fields")),
    P("maintenance.subject_logged", "Item or room maintenance logged", ("log_id", "schedule_id", "subject_type")),
)
