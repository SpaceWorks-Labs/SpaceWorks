"""Account-merge dispositions for lane L12 (machines and loans depth, release 2)."""

from .merge_registry_types import REPOINT as R, UNIQUE_RESOLVE as U

_MUTABLE = "Mutable ownership or attribution; moves to the survivor."

ROWS = (
    (U, "hardware_requests.LoanWaitlistEntry", "user",
     "One live waitlist place per person and item; survivor wins, the loser's place stays on the shell."),
    (R, "procurement.Vendor", "created_by", _MUTABLE),
    (R, "machines.MachineJobBatch", "started_by", _MUTABLE),
    (R, "machines.MachineDowntime", "started_by ended_by", _MUTABLE),
    (R, "maintenance.WorkOrder", "assignee created_by closed_by", _MUTABLE),
)
