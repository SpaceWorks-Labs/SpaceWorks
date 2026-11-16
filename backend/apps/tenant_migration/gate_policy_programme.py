"""Single-command scope setup is distinct from a sweep performing one write per tenant."""

MULTI_SCOPE_BOUNDARIES = frozenset({
    "apps.events.clone_preparation.prepare",
    "apps.events.website_preparation.prepared_page_write",
    "apps.events.profile_photos.purge_scope.presentation_purge_scope",
    "apps.accounts.erasure_hooks.erasure_scope",
    "apps.events.profile_photos.deletion.delete_source",
    "apps.events.services_write_boundary.write_boundary",
    "apps.events.credentials.boundary.event_command",
    "apps.events.hackathons.admission_maintenance.maintenance_boundary",
    "apps.events.hackathons.admission_transactions.command",
    "apps.integrations.notification_attachment_sources.attachment_source_boundary",
    "apps.integrations.notification_media._source_boundaries",
})
