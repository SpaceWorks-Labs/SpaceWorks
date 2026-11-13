"""Global organization IDs in audit metadata remain source-local provenance."""


def declarations(reference, source_local):
    return reference(
        source_local, "organizations.Organization",
        ("event.organizers_updated", "old_organization_ids"),
        ("event.organizers_updated", "organization_ids"),
        ("event.audience_updated", "organization_ids"),
        ("event.audience_organizations_updated", "old_organization_ids"),
        ("event.audience_organizations_updated", "organization_ids"),
        ("event.series_audience_updated", "organization_ids"),
        ("organization.invitation_created", "organization_id"),
        ("organization.invitation_redeemed", "organization_id"),
        ("organization.invitation_revoked", "organization_id"),
    )
