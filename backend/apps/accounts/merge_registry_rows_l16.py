"""Account-merge dispositions for lane L16 (technicians, issue reports and repairs, release 2)."""

from .merge_registry_types import KEEP_ON_SHELL as K, REPOINT as R, UNIQUE_RESOLVE as U

_HISTORY = "Append-only repair history and evidence; stays on the shell (read through the alias)."

ROWS = (
    (U, "maintenance.TechnicianContact", "person",
     "One technician contact per person and space; survivor wins, the loser's contact stays on the shell."),
    (U, "maintenance.IssueAssignment", "person",
     "One assignment per person and issue; survivor wins, the loser's duplicate stays on the shell."),
    (R, "maintenance.IssueReport", "reporter", "The reporter owns the report and its fixed notice."),
    (R, "maintenance.RoomOutage", "started_by ended_by", "Mutable outage attribution; moves to the survivor."),
    (K, "maintenance.IssueEvent", "actor", _HISTORY),
    (K, "maintenance.IssuePhoto", "uploaded_by", _HISTORY),
    (K, "maintenance.TechnicianDispatch", "sent_by", _HISTORY),
    (K, "maintenance.SubjectMaintenanceLog", "performed_by", _HISTORY),
)
