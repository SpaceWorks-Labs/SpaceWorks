"""Approved parity capabilities, picked up by the installer through their parents."""


def definitions(FeatureDefinition):
    features = (FeatureDefinition(
        "bookings.analytics", "bookings", "Resource analytics",
        "Read calendar reservation utilization for one resource with management and audit authority.",
        requires_modules=("bookings", "reports"),
    ), FeatureDefinition(
        "bookings.utilization_pdf", "bookings", "Resource utilization PDF",
        "Download an audited bounded-period resource utilization PDF as a tenant booking manager.",
        requires_modules=("bookings", "reports"), requires_features=("bookings.analytics",),
    ), FeatureDefinition(
        "bookings.exports", "bookings", "Resource reservation exports",
        "Preview and export tenant-local reservation contacts and custom answers with management and audit authority.",
        requires_modules=("bookings", "reports"),
    ), FeatureDefinition(
        "bookings.staff_grants", "bookings", "Resource staff grants",
        "Delegate descriptive editing, reservations, arrival or page release for one resource.",
        requires_modules=("bookings",),
    ), FeatureDefinition(
        "events.organization_audience", "events", "Participating organizations audience",
        "Admit active accounts belonging to live event organizers or the venue owner, "
        "directly or through their owned makerspaces. Imported audiences need local review.",
        requires_modules=("events",),
    ), FeatureDefinition(
        "events.broadcasts", "events", "Event broadcasts",
        "Send durable email campaigns to verified event registrants with live authority checks.",
        requires_modules=("events", "notifications", "email"),
    ), FeatureDefinition(
        "reports.event_pdf", "reports", "Post-event PDF",
        "Download an audited post-event analytics PDF through the report registry.",
        requires_modules=("events", "reports"),
    ), FeatureDefinition(
        "reports.event_exports", "reports", "Event detail exports",
        "Export tenant-local registrations and feedback with event management and audit authority.",
        requires_modules=("events", "reports"),
    ))
    from apps.separability.tombstones import tombstoned_app_labels
    unavailable = tombstoned_app_labels()
    return tuple(feature for feature in features if not set(feature.requires_modules) & unavailable)
