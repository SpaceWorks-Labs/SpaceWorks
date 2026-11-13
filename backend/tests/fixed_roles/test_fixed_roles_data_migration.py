"""Upgrade real historical rows through schema, data, and constraint migrations."""
import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.makerspaces.role_migration_mapping import FROZEN_CATALOG
from tests.fixed_roles.migration_helpers import old_database, historical_world, upgrade

pytestmark = pytest.mark.django_db(transaction=True)


def test_upgrade_maps_roles_references_scopes_and_collision_names(old_database):
    world = historical_world(old_database)
    new = upgrade()
    role_model = new.get_model("makerspaces", "MakerspaceRole")
    membership_model = new.get_model("makerspaces", "MakerspaceMembership")
    additional_model = new.get_model("makerspaces", "MembershipAdditionalRole")
    scope_model = new.get_model("machines", "MembershipMachineTypeScope")
    logs = new.get_model("audit", "AuditLog").objects.filter(makerspace_id=world["space"].pk)
    catalogue = {row.slug: row for row in role_model.objects.filter(makerspace_id=world["space"].pk)}
    assert set(catalogue) == {row[0] for row in FROZEN_CATALOG}
    for slug, name, legacy, actions in FROZEN_CATALOG:
        row = catalogue[slug]
        assert (row.name, row.legacy_role, row.granted_actions, row.is_default, row.is_protected) == (
            name, legacy, sorted(actions), True, True,
        )
    # Surviving defaults retain identity even after swapped names; obsolete rows
    # occupying canonical names/slugs are replaced, never mistaken for defaults.
    for slug in ("space_manager", "inventory_manager", "machine_manager", "member"):
        assert catalogue[slug].pk == world["roles"][slug].pk
    for slug in ("event_manager", "handover"):
        assert catalogue[slug].pk != world["roles"][slug].pk
    assert not role_model.objects.filter(slug="print_manager").exists()

    def role_set(label):
        row = membership_model.objects.get(pk=world["memberships"][label].pk)
        result = [role_model.objects.get(pk=row.assigned_role_id).slug] if row.assigned_role_id else []
        result += list(additional_model.objects.filter(membership_id=row.pk).values_list("role__slug", flat=True))
        return set(result)

    assert role_set("space_manager") == {"space_manager"}
    assert role_set("inventory_manager") == {"inventory_manager", "booking_manager"}
    assert role_set("inventory-events") == {"inventory_manager", "event_manager"}
    assert role_set("handover") == {"handover"}
    assert role_set("print_manager") == {"member"}
    assert role_set("foreign") == {"member"}
    assert role_set("legacy") == set()
    legacy = membership_model.objects.get(pk=world["memberships"]["legacy"].pk)
    assert legacy.role == "machine_manager" and legacy.assigned_role_id is None

    def type_ids(label):
        return set(scope_model.objects.filter(membership_id=world["memberships"][label].pk).values_list("machine_type_id", flat=True))

    assert type_ids("typed") == {world["kind"].pk}
    assert type_ids("typed-peer") == {world["kind"].pk}
    assert membership_model.objects.get(pk=world["memberships"]["inventory-events"].pk).status == "revoked"
    assert role_set("typed") == {"machine_manager"}
    assert type_ids("exempt") == world["all_type_ids"]
    assert world["foreign_kind"].pk not in type_ids("exempt")
    assert role_set("machine-only") == {"member"}
    assert type_ids("machine-only") == set()
    assert role_set("empty") == {"machine_manager"}
    assert type_ids("empty") == set()
    evidence = {row.meta["membership_id"]: row.meta for row in logs.filter(action="staff.roles_migrated")
                if "membership_id" in row.meta}
    typed = evidence[world["memberships"]["typed"].pk]
    assert typed["machine_scope"]["to"] == {"types": [world["kind"].pk], "machines": []}
    assert typed["machine_scope"]["dropped_machine_ids"] == [world["machine"].pk]
    dropped = evidence[world["memberships"]["machine-only"].pk]
    assert dropped["machine_scope_outcome"] == "machine_manager_dropped: machine-only scope"
    assert evidence[world["memberships"]["exempt"].pk]["machine_scope"]["exempt_enumerated"] is True
    assert evidence[world["memberships"]["space_manager"].pk]["exception_tags"] == ["E1"]
    assert evidence[world["memberships"]["handover"].pk]["gained_actions"] == ["collect_service_request"]
    assert world["memberships"]["legacy"].pk not in evidence

    request_model = new.get_model("makerspaces", "MembershipRequest")
    for state, old in world["requests"].items():
        request = request_model.objects.get(pk=old.pk)
        expected = ("inventory_manager" if state == "closed-default" else
                    "member" if state in {"active", "revoked"} else "event_manager")
        assert request.assigned_role_id == (None if state == "null" else catalogue[expected].pk)
        assert request.state == old.state
    invitation_model = new.get_model("accounts", "StaffInvitation")
    valid = invitation_model.objects.get(pk=world["invitations"]["valid"].pk)
    assert valid.revoked_at is None
    assert valid.role_id == catalogue["inventory_manager"].pk
    assert valid.granted_actions == catalogue["inventory_manager"].granted_actions
    assert valid.expires_at == world["invitations"]["valid"].expires_at
    assert valid.failed_attempts == 2
    assert valid.token_digest == world["invitations"]["valid"].token_digest
    for label in ("stale", "e2"):
        row = invitation_model.objects.get(pk=world["invitations"][label].pk)
        assert row.revoked_at is not None and row.role_id == catalogue["member"].pk
        assert row.granted_actions == world["invitations"][label].granted_actions
        assert row.expires_at == world["invitations"][label].expires_at
        assert row.failed_attempts == 2
        assert logs.filter(action="staff.invitation_revoked_by_migration", meta__invitation_id=row.pk).exists()
    closed = invitation_model.objects.get(pk=world["invitations"]["closed"].pk)
    assert closed.accepted_at is not None and closed.revoked_at is None
    assert closed.role_id == catalogue["member"].pk
    schedule_model = new.get_model("operations", "ReportSchedule")
    for label, old in world["schedules"].items():
        row = schedule_model.objects.get(pk=old.pk)
        assert row.recipient_roles == (["space_manager"] if label == "mixed" else [])
        assert row.is_active is (label != "empty")
        audit = logs.get(action="report_schedule.recipients_pruned_by_migration", meta__schedule_id=row.pk)
        assert audit.meta["before_roles"] == old.recipient_roles
        assert audit.meta["after_roles"] == row.recipient_roles
        assert audit.meta["deactivated"] is (label == "empty")
    # The production finish installs the DB fence and drops the old role tables.
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())
    tables = connection.introspection.table_names()
    assert "machines_rolemachinescope" not in tables
    assert "machines_rolemachinetypescope" not in tables


def test_custom_role_recipient_refuses_before_any_data_changes(old_database):
    world = historical_world(old_database)
    model = old_database.get_model
    rule = model("integrations", "NotificationRecipient").objects.create(
        makerspace=world["space"], feature="maintenance", event="logged", kind="role", role=world["roles"]["typed"],
    )
    labels = [("makerspaces", "MakerspaceRole"), ("makerspaces", "MakerspaceMembership"),
              ("makerspaces", "MembershipRequest"), ("accounts", "StaffInvitation"),
              ("operations", "ReportSchedule"), ("audit", "AuditLog"),
              ("machines", "RoleMachineTypeScope"), ("machines", "RoleMachineScope"),
              ("integrations", "NotificationRecipient")]
    snapshot = lambda: {label: list(model(*label).objects.order_by("pk").values()) for label in labels}
    before = snapshot()
    try:
        with pytest.raises(RuntimeError, match="must fix before upgrading") as error:
            upgrade()
        assert f"recipient={rule.pk}" in str(error.value)
        assert snapshot() == before
    finally:
        # Leave the historical schema unblocked for the fixture's forward restore.
        model("integrations", "NotificationRecipient").objects.filter(pk=rule.pk).delete()
