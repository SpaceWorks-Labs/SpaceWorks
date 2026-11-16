"""Release-2 lane L16 (technicians, issue reports, repairs, item/room maintenance): tenant-dump
field snapshot and authority.

Every row is the space's own operational record (data_export `classification_l16`) and
travels with it; foreign keys remap like any other. Two things never travel as live:
the opt-in link digest (a bearer credential) and chat consent, which was given against
the source deployment's senders -- a moved technician opts in again on the target.
"""

from apps.data_export.classification_l16 import EXPORTED_FIELDS

FIELD_NAMES = {label: frozenset(names.split()) for label, names in EXPORTED_FIELDS.items()}
EXTRA_FIELDS = {}
PROJECTED_LABELS = frozenset(FIELD_NAMES)


def authority_entries(authority, disposition):
    def same(label, names, chosen, reason):
        return tuple(((label, name), authority(chosen, reason)) for name in names.split())

    keep, reset = disposition.PRESERVE, disposition.RESET
    return (
        *same("maintenance.TechnicianContact", "kind name email phone telegram_handle channels notes is_archived "
              "created_at updated_at", keep, "A technician entry is the space's own directory record."),
        *same("maintenance.TechnicianContact", "telegram_chat_id telegram_opted_in_at whatsapp_opted_in_at "
              "sms_opted_in_at opt_in_digest opt_in_expires_at", reset,
              "Chat consent and the opt-in link belong to the source deployment's senders."),
        *same("maintenance.TechnicianCoverage", "kind", keep, "Coverage names what the technician looks after."),
        *same("maintenance.TechnicianDefault", "area", keep, "Pre-selected recipients are the space's policy."),
        *same("maintenance.IssueReport", "area subject_type source reporter_name reporter_email title description "
              "state priority resolution quote_state quote_amount quote_currency quote_note reporter_notified_at "
              "fixed_at closed_at created_at updated_at", keep, "An issue and its repair are the space's own record."),
        *same("maintenance.IssueAssignment", "created_at", keep, "Who works an issue is part of its record."),
        *same("maintenance.IssueEvent", "kind note occurred_on amount currency created_at", keep,
              "The append-only repair history."),
        *same("maintenance.IssuePhoto", "stage object_key content_type size_bytes created_at", keep,
              "A private repair photo and its stage."),
        *same("maintenance.TechnicianDispatch", "channel status failure_code provider_message_id sent_at", keep,
              "The append-only record of every send to a technician."),
        *same("maintenance.RepairPart", "kind name quantity created_at", keep, "Parts used and needed on a repair."),
        *same("maintenance.RoomOutage", "mode reason expected_back_at started_at ended_at", keep,
              "A room's out-of-service history."),
        *same("maintenance.SubjectMaintenanceSchedule", "subject_type description interval_days next_due is_active "
              "created_at updated_at", keep, "An item or room maintenance schedule is the space's own policy."),
        *same("maintenance.SubjectMaintenanceLog", "subject_type performed_at summary parts_note cost created_at", keep,
              "The append-only maintenance log."),
    )
