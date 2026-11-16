"""Booking read vocabulary is core metadata, independent of the runtime app."""

RESOURCE_READ = "booking_resources:read"
BOOKING_READ = "bookings:read"
ARRIVAL_READ = "bookings:attendance:read"
PREFIX = "/api/v1/booking-integration/"


def booking_read_scopes():
    from apps.separability.tombstones import tombstoned_app_labels
    return frozenset() if "bookings" in tombstoned_app_labels() else frozenset({
        RESOURCE_READ, BOOKING_READ, ARRIVAL_READ,
    })


def booking_read_routes():
    from .scope_registry_routes import ScopeRegistryEntry, TARGET_CLIENT_SUBJECT
    if not booking_read_scopes():
        return {}
    resource = ScopeRegistryEntry(frozenset({RESOURCE_READ}), TARGET_CLIENT_SUBJECT,
                                 server_only=True, tenant_bound=True)
    booking = ScopeRegistryEntry(frozenset({BOOKING_READ, ARRIVAL_READ}), TARGET_CLIENT_SUBJECT,
                                server_only=True, tenant_bound=True,
                                required_scopes=frozenset({BOOKING_READ}))
    return {(name, method): entry for name, entry in (
        ("integration-booking-resource-list", resource),
        ("integration-booking-resource-detail", resource),
        ("integration-booking-list", booking),
        ("integration-booking-detail", booking),
        ("integration-booking-resource-reservations", booking),
    ) for method in ("GET", "HEAD")}


def booking_read_catalog():
    return tuple((value, label, description) for value, label, description in (
        (RESOURCE_READ, "Booking resource read", "Read minimal resources through tenant-bound signed server routes."),
        (BOOKING_READ, "Booking read", "Read reservation IDs, resources, windows, status and display name."),
        (ARRIVAL_READ, "Booking arrival read", "Include current arrival dates; requires bookings:read."),
    ) if value in booking_read_scopes())
