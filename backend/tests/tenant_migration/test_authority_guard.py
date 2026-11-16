import pytest

from apps.tenant_migration.authority_guards import (
    DECLARED_AUTHORITY_FIELDS,
    AuthorityRegistryError,
    discover_exported_authority_fields,
    validate_authority_registry,
)


def test_complete_authority_registry_is_valid():
    validate_authority_registry()


def test_every_replay_field_has_an_explicit_drop_override():
    from apps.tenant_migration.tenant_dump_authority import AUTHORITY_FIELD_OVERRIDES
    from apps.tenant_migration.tenant_dump_field_snapshot import FIRST_PARTY_FIELD_NAMES
    from apps.tenant_migration.tenant_dump_types import AuthorityDisposition
    label = "hardware_requests.ReplayCommand"
    for name in FIRST_PARTY_FIELD_NAMES[label]:
        assert AUTHORITY_FIELD_OVERRIDES[(label, name)].dispositions == (AuthorityDisposition.DROP,)


def test_mechanically_discovered_authority_inputs_are_explicit():
    assert discover_exported_authority_fields() <= set(DECLARED_AUTHORITY_FIELDS)


@pytest.mark.parametrize("label", ["makerspaces.Makerspace", "machines.Machine"])
def test_broadcast_location_overapproximation_is_explicit(label):
    edge = (label, "location")
    assert edge in discover_exported_authority_fields()
    assert edge in DECLARED_AUTHORITY_FIELDS
    changed = dict(DECLARED_AUTHORITY_FIELDS)
    changed.pop(edge)
    with pytest.raises(AuthorityRegistryError, match="authorization inputs are undeclared"):
        validate_authority_registry(changed, required_fields=())


def test_locked_role_authority_modules_remain_in_the_scan():
    from apps.tenant_migration.authority_guards import APPS_DIR, AUTHORIZATION_SOURCES

    assert {
        APPS_DIR / "makerspaces" / "role_authority.py",
        APPS_DIR / "makerspaces" / "role_assignments.py",
        APPS_DIR / "makerspaces" / "role_membership_writes.py",
        APPS_DIR / "accounts" / "rbac_roles.py",
        APPS_DIR / "machines" / "member_scope_services.py",
    } <= set(AUTHORIZATION_SOURCES)


def test_extracted_resource_delegation_locks_remain_in_the_scan():
    from apps.tenant_migration.authority_guards import APPS_DIR, AUTHORIZATION_SOURCES

    path = APPS_DIR / "makerspaces" / "resource_grant_locks.py"
    assert path in AUTHORIZATION_SOURCES
    assert APPS_DIR / "events" / "staff_grant_locks.py" in AUTHORIZATION_SOURCES
    edge = ("makerspaces.MakerspaceMembership", "assigned_role")
    assert edge in discover_exported_authority_fields(paths=(path,))
    changed = dict(DECLARED_AUTHORITY_FIELDS)
    changed.pop(edge)
    with pytest.raises(AuthorityRegistryError, match="authorization inputs are undeclared"):
        validate_authority_registry(changed, paths=(path,), required_fields=())


def test_declared_relational_and_discriminator_authority_inputs():
    required = {
        ("makerspaces.MakerspaceMembership", "role"),
        ("makerspaces.MakerspaceMembership", "assigned_role"),
        ("makerspaces.MakerspaceMembership", "status"),
        ("makerspaces.MakerspaceMembership", "can_verify"),
        ("makerspaces.MakerspaceMembership", "can_refer"),
        ("makerspaces.MakerspaceRole", "granted_actions"),
        ("makerspaces.MakerspaceRole", "slug"),
        ("makerspaces.Makerspace", "slug"),
        ("makerspaces.Makerspace", "public_inventory_enabled"),
        ("machines.MachineType", "slug"),
        ("makerspaces.MakerspaceRole", "is_default"),
        ("makerspaces.MakerspaceRole", "is_protected"),
        ("machines.MachineType", "managing_action"),
        ("machines.MachineOperator", "access_level"),
        ("machines.MachineOperator", "assigned_by"),
        ("machines.MachineOperator", "assigned_at"),
        ("makerspaces.MembershipAdditionalRole", "membership"),
        ("makerspaces.MembershipAdditionalRole", "role"),
        ("machines.MembershipMachineTypeScope", "membership"),
        ("machines.MembershipMachineTypeScope", "machine_type"),
        ("integrations.NotificationRecipient", "kind"),
        ("integrations.NotificationRecipient", "role"),
        ("integrations.NotificationRecipient", "user"),
        ("makerspaces.MembershipRequest", "assigned_role"),
        ("makerspaces.MembershipRequest", "auto_activate_on_claim"),
        ("makerspaces.Station", "created_by"),
    }
    assert required <= set(DECLARED_AUTHORITY_FIELDS)


def test_authority_guard_fails_when_a_discovered_declaration_is_removed():
    changed = dict(DECLARED_AUTHORITY_FIELDS)
    changed.pop(("machines.MachineType", "managing_action"))
    with pytest.raises(AuthorityRegistryError, match="authorization inputs are undeclared"):
        validate_authority_registry(changed, required_fields=())


def test_authority_guard_fails_when_an_explicit_declaration_is_removed():
    changed = dict(DECLARED_AUTHORITY_FIELDS)
    changed.pop(("makerspaces.MakerspaceMembership", "can_verify"))
    with pytest.raises(AuthorityRegistryError, match="required authority declarations"):
        validate_authority_registry(changed)


@pytest.mark.parametrize("label", ["makerspaces.Makerspace", "machines.MachineType"])
def test_routing_identifier_authority_must_remain_declared(label):
    changed = dict(DECLARED_AUTHORITY_FIELDS)
    changed.pop((label, "slug"))
    with pytest.raises(AuthorityRegistryError, match="authorization inputs are undeclared"):
        validate_authority_registry(changed, required_fields=())


def test_fixed_role_and_member_scope_authority_is_dropped_on_portable_import():
    from apps.tenant_migration.tenant_dump_model_catalog import FIRST_PARTY_MODEL_RULES
    from apps.tenant_migration.target_projection_rows import ROW_POLICIES
    from apps.tenant_migration.authority_guards import SCANNED_MODEL_LABELS

    for label in ("makerspaces.MembershipAdditionalRole", "machines.MembershipMachineTypeScope"):
        assert FIRST_PARTY_MODEL_RULES[label].disposition.value == "project"
        assert ROW_POLICIES[label].disposition.value == "drop"
        assert ROW_POLICIES[label].condition == ("_staff_account", False)
        assert label in SCANNED_MODEL_LABELS
    for label in ("machines.RoleMachineScope", "machines.RoleMachineTypeScope"):
        assert label not in FIRST_PARTY_MODEL_RULES
        assert label not in ROW_POLICIES
        assert all(model_label != label for model_label, _ in DECLARED_AUTHORITY_FIELDS)


@pytest.mark.parametrize("label", ["makerspaces.Makerspace", "machines.Machine"])
def test_broadcast_location_overapproximation_is_explicit(label):
    edge = (label, "location")
    assert edge in discover_exported_authority_fields()
    assert edge in DECLARED_AUTHORITY_FIELDS
    changed = dict(DECLARED_AUTHORITY_FIELDS)
    changed.pop(edge)
    with pytest.raises(AuthorityRegistryError, match="authorization inputs are undeclared"):
        validate_authority_registry(changed, required_fields=())


def test_extracted_resource_delegation_locks_remain_in_the_scan():
    from apps.tenant_migration.authority_guards import APPS_DIR, AUTHORIZATION_SOURCES

    path = APPS_DIR / "makerspaces" / "resource_grant_locks.py"
    assert path in AUTHORIZATION_SOURCES
    assert APPS_DIR / "events" / "staff_grant_locks.py" in AUTHORIZATION_SOURCES
    assert APPS_DIR / "bookings" / "booking_authority.py" in AUTHORIZATION_SOURCES
    for edge in (("makerspaces.MakerspaceMembership", "assigned_role"),
                 ("makerspaces.MembershipAdditionalRole", "role")):
        assert edge in discover_exported_authority_fields(paths=(path,))
        changed = dict(DECLARED_AUTHORITY_FIELDS)
        changed.pop(edge)
        with pytest.raises(AuthorityRegistryError, match="authorization inputs are undeclared"):
            validate_authority_registry(changed, paths=(path,), required_fields=())


def test_resource_models_remain_scanned():
    from apps.tenant_migration.authority_guards import SCANNED_MODEL_LABELS

    # Grants themselves are never portable (no exported fields to scan); the exported
    # resources whose relations bound grant authority are.
    assert {"events.Event", "events.EventSeries", "bookings.BookableSpace"} <= SCANNED_MODEL_LABELS
    for edge in (("events.Event", "makerspace"), ("events.Event", "series"),
                 ("bookings.BookableSpace", "makerspace")):
        assert edge in discover_exported_authority_fields()
        changed = dict(DECLARED_AUTHORITY_FIELDS)
        changed.pop(edge)
        with pytest.raises(AuthorityRegistryError):
            validate_authority_registry(changed)
