"""Origin-scope table for release 2 L16's staff routes that name only a row.

Routes with `makerspace_id` in the URL already resolve their target; these name an issue,
a technician, an item/room schedule or a machine schedule, so their target is that row's
own space and a verified custom staff origin pins them like every other admin route.
"""

_ISSUE = ("maintenance.IssueReport", "makerspace_id")

MODEL_LOOKUPS = {
    **{name: _ISSUE for name in (
        "admin-issue-detail", "admin-issue-triage", "admin-issue-reject", "admin-issue-assign", "admin-issue-unassign",
        "admin-issue-dispatch", "admin-issue-start", "admin-issue-work-log", "admin-issue-parts", "admin-issue-quote",
        "admin-issue-approve", "admin-issue-payout", "admin-issue-fix", "admin-issue-close",
    )},
    **{name: ("maintenance.TechnicianContact", "makerspace_id") for name in (
        "admin-technician-detail", "admin-technician-opt-in-link", "admin-technician-consent")},
    "admin-subject-maintenance-detail": ("maintenance.SubjectMaintenanceSchedule", "makerspace_id"),
    "admin-subject-maintenance-run": ("maintenance.SubjectMaintenanceSchedule", "makerspace_id"),
    "admin-machine-maintenance-run": ("maintenance.MaintenanceSchedule", "machine__makerspace_id"),
}
