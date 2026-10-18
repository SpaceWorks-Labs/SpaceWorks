"""Single-command scope setup is distinct from a sweep performing one write per tenant."""

MULTI_SCOPE_BOUNDARIES = frozenset({
    "apps.events.credentials.boundary.event_command",
    "apps.events.hackathons.admission_maintenance.maintenance_boundary",
    "apps.events.hackathons.admission_transactions.command",
    "apps.integrations.notification_attachment_sources.attachment_source_boundary",
    "apps.integrations.notification_media._source_boundaries",
})
