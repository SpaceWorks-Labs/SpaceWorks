"""Deployment-global uniqueness for lane L12's rows.

A vendor's live name and the reservation policy are unique within the space (no rule).
A member's live waitlist place is unique per item and person: it follows the remapped
item and account once.
"""

from .unique_values_policy import REMAP, _policy

RULES = {
    ("hardware_requests.LoanWaitlistEntry", "uniq_active_waitlist_entry"): _policy(
        REMAP, "One live waitlist place per item and person; follows the imported item and account."),
    ("machines.MachineDowntime", "machine_downtime_one_open"): _policy(
        REMAP, "One open downtime period per machine; follows the imported machine."),
}
