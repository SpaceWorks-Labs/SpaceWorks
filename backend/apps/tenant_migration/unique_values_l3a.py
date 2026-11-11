"""Deployment-global uniqueness for release 0.12.0 lane L3a's rows.

Each constraint is per event, certification, machine, session or person, so it follows the
remapped rows once, like every other per-row unique.
"""

from .unique_values_policy import REMAP, _policy

RULES = {
    ("machines.EventInductionLink", "induction_link_uniq"): _policy(
        REMAP, "One induction link per event and certification; follows the imported event and type."),
    ("machines.SupervisedSession", "supervised_session_one_open_per_machine"): _policy(
        REMAP, "One open supervised session per machine; follows the imported machine."),
}
