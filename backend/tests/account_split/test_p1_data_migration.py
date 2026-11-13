"""D12 cutover drops old mixed-account authority without moving community records."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

pytestmark = pytest.mark.django_db(transaction=True)


def _targets_before(graph, pin):
    """Each app's newest migration that needs nothing in `pin`'s app after `pin`.

    Pinning only accounts while keeping every other leaf made a mixed forwards/backwards
    plan once later apps' leaves came to depend on newer accounts migrations.
    """
    allowed = set(graph.forwards_plan(pin))
    blocked = {node for node in graph.nodes if node[0] == pin[0] and node not in allowed}
    targets = {}
    for node in graph.nodes:
        plan = graph.forwards_plan(node)
        if blocked.intersection(plan):
            continue
        best = targets.get(node[0])
        if best is None or len(plan) > len(graph.forwards_plan(best)):
            targets[node[0]] = node
    targets[pin[0]] = pin
    return sorted(targets.values())


def test_dev_data_classification_and_staff_role_stripping():
    executor = MigrationExecutor(connection)
    latest = executor.loader.graph.leaf_nodes()
    before = _targets_before(executor.loader.graph, ("accounts", "0031_platformloginmethods_provider_switches"))
    try:
        executor.migrate(before)
        state = executor.loader.project_state(before).apps
        User = state.get_model("accounts", "User")
        Space = state.get_model("makerspaces", "Makerspace")
        Role = state.get_model("makerspaces", "MakerspaceRole")
        Membership = state.get_model("makerspaces", "MakerspaceMembership")
        Additional = state.get_model("makerspaces", "MembershipAdditionalRole")
        root = User.objects.create(username="migration-root", is_superuser=True, role="superadmin")
        mixed = User.objects.create(username="migration-mixed", role="space_manager")
        space = Space.objects.create(name="Migration", slug="migration")
        member, handover, inventory = [Role.objects.create(makerspace=space, name=slug, slug=slug,
            is_default=True, is_protected=True, granted_actions=[]) for slug in ("member", "handover", "inventory_manager")]
        membership = Membership.objects.create(user=mixed, makerspace=space, assigned_role=handover, role="handover")
        Additional.objects.create(membership=membership, role=inventory)
        Membership.objects.create(user=root, makerspace=space, assigned_role=member, role="custom")
        # Recreate the executor after each graph transition; cached applied state is stale.
        executor = MigrationExecutor(connection)
        executor.migrate(latest)
        state = executor.loader.project_state(latest).apps
        User = state.get_model("accounts", "User")
        Membership = state.get_model("makerspaces", "MakerspaceMembership")
        assert User.objects.get(pk=root.pk).account_kind == "platform"
        assert User.objects.get(pk=mixed.pk).account_kind == "member"
        assert not Membership.objects.filter(user_id=root.pk).exists()
        after = Membership.objects.get(pk=membership.pk)
        assert after.user_id == mixed.pk and after.assigned_role_id == member.pk and after.role == "custom"
        assert not state.get_model("makerspaces", "MembershipAdditionalRole").objects.exists()
    finally:
        MigrationExecutor(connection).migrate(latest)
