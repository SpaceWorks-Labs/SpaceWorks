"""Privileged read scopes and route entries; domain runtime can disappear."""

EVENT_READ = "events:read"
PARTICIPANT_READ = "participants:read"
ATTENDANCE_READ = "participants:attendance:read"


def read_scope_vocabulary():
    from apps.separability.tombstones import tombstoned_app_labels
    if "events" in tombstoned_app_labels():
        return frozenset()
    return frozenset({EVENT_READ, PARTICIPANT_READ, ATTENDANCE_READ})


def read_route_entries():
    from .scope_registry_routes import ScopeRegistryEntry, TARGET_CLIENT_SUBJECT
    if EVENT_READ not in read_scope_vocabulary():
        return {}
    basic = ScopeRegistryEntry(
        frozenset({EVENT_READ}), TARGET_CLIENT_SUBJECT,
        server_only=True, tenant_bound=True,
    )
    participants = ScopeRegistryEntry(
        frozenset({PARTICIPANT_READ, ATTENDANCE_READ}), TARGET_CLIENT_SUBJECT,
        server_only=True, tenant_bound=True,
        required_scopes=frozenset({EVENT_READ, PARTICIPANT_READ}),
    )
    return {(name, method): entry for name, entry in (
        ("integration-event-list", basic), ("integration-event-detail", basic),
        ("integration-event-participants", participants),
    ) for method in ("GET", "HEAD")}
