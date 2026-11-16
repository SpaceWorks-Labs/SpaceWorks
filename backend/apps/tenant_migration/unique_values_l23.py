"""Deployment-global uniqueness for lane L23's rows.

The live-session and one-confirm constraints are per machine, member, job or session: they
follow the remapped rows once, like every other per-row partial unique.
"""

from .unique_values_policy import REMAP, _policy

RULES = {
    ("machines.MachineSession", "machine_session_one_live_per_machine"): _policy(
        REMAP, "One live session per machine; follows the imported machine."),
    ("machines.MachineSession", "machine_session_one_live_per_member_machine"): _policy(
        REMAP, "One live session per member and machine; follows the imported machine and account."),
    ("machines.MachineSession", "machine_session_one_device_session_per_job"): _policy(
        REMAP, "One device session per machine job; follows the imported job."),
    ("machines.MachineSessionAmendment", "machine_session_one_confirm"): _policy(
        REMAP, "One staff confirmation per session; follows the imported session."),
}
