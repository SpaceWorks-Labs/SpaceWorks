"""Reviewed L16 dynamic audit sites; their metadata is denied by default.

Every repair-timeline step goes through ``maintenance/repairs/history.step``, whose action
is a parameter, so those actions take the wrapper's deny policy: no catalogue label and
``meta={}`` in staff views, while the raw audit row keeps the full metadata.
"""

# services_contacts picks set/removed by branch.
EXACT = frozenset(("technician.default_set", "technician.default_removed"))
# service_state passes a built dict; maintenance_subjects keys the subject id by type.
NON_LITERAL = frozenset(("maintenance.subject_schedule_created", "service_state.changed"))
WRAPPERS = {
    "maintenance/repairs/history.py": (
        "issue.reported", "issue.opened", "issue.triaged", "issue.rejected", "issue.assigned",
        "issue.unassigned", "issue.closed", "dispatch.sent", "repair.", "service_state.changed",
    ),
}
