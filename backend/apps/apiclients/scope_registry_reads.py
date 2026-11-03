"""Privileged read scopes and route entries; domain runtime can disappear."""

EVENT_READ = "events:read"
PARTICIPANT_READ = "participants:read"
ATTENDANCE_READ = "participants:attendance:read"
#: Release 2 L6 (G35): ticket orders -- totals, lines and seat counts, never contacts.
ORDER_READ = "orders:read"


def read_scope_vocabulary():
    from .scope_registry_booking_reads import booking_read_scopes
    from apps.separability.tombstones import tombstoned_app_labels
    if "events" in tombstoned_app_labels():
        return booking_read_scopes()
    return frozenset({EVENT_READ, PARTICIPANT_READ, ATTENDANCE_READ, ORDER_READ}) | booking_read_scopes()


def read_route_entries():
    from .scope_registry_booking_reads import booking_read_routes
    from .scope_registry_routes import ScopeRegistryEntry, TARGET_CLIENT_SUBJECT
    if EVENT_READ not in read_scope_vocabulary():
        return booking_read_routes()
    basic = ScopeRegistryEntry(
        frozenset({EVENT_READ}), TARGET_CLIENT_SUBJECT,
        server_only=True, tenant_bound=True,
    )
    participants = ScopeRegistryEntry(
        frozenset({PARTICIPANT_READ, ATTENDANCE_READ}), TARGET_CLIENT_SUBJECT,
        server_only=True, tenant_bound=True,
        required_scopes=frozenset({EVENT_READ, PARTICIPANT_READ}),
    )
    orders = ScopeRegistryEntry(
        frozenset({ORDER_READ}), TARGET_CLIENT_SUBJECT,
        server_only=True, tenant_bound=True,
    )
    return booking_read_routes() | {(name, method): entry for name, entry in (
        ("integration-event-list", basic), ("integration-event-detail", basic),
        ("integration-event-participants", participants),
        ("integration-order-list", orders), ("integration-order-detail", orders),
    ) for method in ("GET", "HEAD")}
