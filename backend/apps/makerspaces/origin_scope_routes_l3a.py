"""Origin-scope table for release 0.12.0 lane L3a's staff routes that name only a row.

Routes carrying `makerspace_id` already resolve their target; these name an induction link,
a guest certification, an incident or an action, so the target is that row's own space and
a verified custom staff origin pins them.
"""

MODEL_LOOKUPS = {
    "admin-event-induction-unlink": ("machines.EventInductionLink", "makerspace_id"),
    "admin-guest-certification-revoke": ("machines.GuestCertificationGrant", "makerspace_id"),
    "admin-incident-detail": ("maintenance.Incident", "makerspace_id"),
    "admin-incident-actions": ("maintenance.Incident", "makerspace_id"),
    "admin-incident-assignees": ("maintenance.Incident", "makerspace_id"),
    "admin-incident-action-detail": ("maintenance.IncidentAction", "incident__makerspace_id"),
}
