"""Release-2 lane L16 (technicians, issue reports, repairs, item/room maintenance): literal export classification.

Every L16 row is the space's own operational record and exports with the space:

* the technician directory (a contractor's phone, email and handles are scoped PII, like
  a borrower's contact snapshot), its coverage and the per-area defaults;
* issue reports with their append-only history, photos (private bucket), technician
  sends, parts, assignments and the payout's ledger link;
* room outages and the item/room maintenance schedules and logs.

Omitted: the opt-in link digest (a live bearer credential) and the Telegram chat id, which
was proven against THIS deployment's bot and means nothing on another.
"""

from .types import TenantPredicate as P

EXPORTED_FIELDS = {
    "maintenance.TechnicianContact": "id makerspace kind person name email phone telegram_handle channels "
                                     "telegram_chat_id telegram_opted_in_at whatsapp_opted_in_at sms_opted_in_at "
                                     "opt_in_digest opt_in_expires_at notes is_archived created_at updated_at",
    "maintenance.TechnicianCoverage": "id contact kind machine_type room",
    "maintenance.TechnicianDefault": "id makerspace area machine_type room contact",
    "maintenance.IssueReport": "id makerspace area subject_type machine product asset room source loan booking "
                               "machine_job machine_session return_line reporter reporter_name reporter_email title description "
                               "state priority work_order resolution quote_state quote_amount quote_currency "
                               "quote_note quote_contact payout_entry reporter_notified_at fixed_at closed_at created_at "
                               "updated_at",
    "maintenance.IssueAssignment": "id issue contact person created_at",
    "maintenance.IssueEvent": "id issue kind actor contact note occurred_on amount currency created_at",
    "maintenance.IssuePhoto": "id issue stage object_key content_type size_bytes uploaded_by created_at",
    "maintenance.TechnicianDispatch": "id issue contact channel status failure_code provider_message_id sent_by "
                                      "sent_at",
    "maintenance.RepairPart": "id issue kind product name quantity to_buy_item created_at",
    "maintenance.RoomOutage": "id makerspace room mode reason expected_back_at issue started_at started_by ended_at "
                              "ended_by",
    "maintenance.SubjectMaintenanceSchedule": "id makerspace subject_type product asset room description "
                                              "interval_days next_due is_active created_at updated_at",
    "maintenance.SubjectMaintenanceLog": "id makerspace schedule subject_type product asset room performed_by "
                                         "performed_at summary parts_note cost created_at",
}
OMITTED_FIELDS = {
    ("maintenance.TechnicianContact", "opt_in_digest"): "Live one-time opt-in link credential; re-sent on the target.",
    ("maintenance.TechnicianContact", "telegram_chat_id"): (
        "Chat proven against this deployment's bot; the technician opts in again on the target."),
}
NON_CREDENTIAL = {
    ("maintenance.IssueReport", "state"): "The issue's workflow state.",
    ("maintenance.IssueReport", "quote_state"): "Whether the repair quote is pending, approved or declined.",
}
DATASET_SPECS = {
    "maintenance.TechnicianContact": ("repairs/technicians.csv", P(("makerspace",))),
    "maintenance.TechnicianCoverage": ("repairs/technician_coverage.csv", P(("contact__makerspace",))),
    "maintenance.TechnicianDefault": ("repairs/technician_defaults.csv", P(("makerspace",))),
    "maintenance.IssueReport": ("repairs/issues.csv", P(("makerspace",))),
    "maintenance.IssueAssignment": ("repairs/assignments.csv", P(("issue__makerspace",))),
    "maintenance.IssueEvent": ("repairs/history.csv", P(("issue__makerspace",))),
    "maintenance.IssuePhoto": ("repairs/photos.csv", P(("issue__makerspace",))),
    "maintenance.TechnicianDispatch": ("repairs/dispatches.csv", P(("issue__makerspace",))),
    "maintenance.RepairPart": ("repairs/parts.csv", P(("issue__makerspace",))),
    "maintenance.RoomOutage": ("repairs/room_outages.csv", P(("makerspace",))),
    "maintenance.SubjectMaintenanceSchedule": ("maintenance/item_room_schedules.csv", P(("makerspace",))),
    "maintenance.SubjectMaintenanceLog": ("maintenance/item_room_logs.csv", P(("makerspace",))),
}
RELATIONAL_USER_FIELDS = frozenset({
    ("maintenance.TechnicianContact", "person"),
    ("maintenance.IssueReport", "reporter"),
    ("maintenance.IssueAssignment", "person"),
    ("maintenance.IssueEvent", "actor"),
    ("maintenance.IssuePhoto", "uploaded_by"),
    ("maintenance.TechnicianDispatch", "sent_by"),
    ("maintenance.RoomOutage", "started_by"),
    ("maintenance.RoomOutage", "ended_by"),
    ("maintenance.SubjectMaintenanceLog", "performed_by"),
})
# A contact's chosen channel names; no ids.
JSON_FIELDS = frozenset({("maintenance.TechnicianContact", "channels")})
OMITTED_MODELS = {}


def extend(fields):
    fields.update(EXPORTED_FIELDS)
    return fields
