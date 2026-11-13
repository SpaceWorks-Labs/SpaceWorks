"""Part B5 ??? retire the default Print Manager role without breaking printing."""
from django.db import IntegrityError, connection, transaction
from tests.accounts.account_factories import make_staff as staff_account
from importlib import import_module
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.accounts import rbac
from apps.accounts.models import User
from apps.integrations.models import EmailNotificationMute
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole
from tests.return_helpers import authenticated_client, make_member, make_space, make_user


pytestmark = pytest.mark.django_db


def _default_role(makerspace, legacy_role):
    return MakerspaceRole.objects.get(makerspace=makerspace, legacy_role=legacy_role)


def test_machine_manager_implies_printing_for_actions_scopes_and_permission():
    makerspace = make_space("b5-machine-scope")
    # U-A1: a staff role is a staff-track row on the person's one account.
    actor = staff_account(makerspace, username="b5-machine-scope-user", role_slug="machine_manager")

    assert rbac.actions_satisfying(rbac.Action.MANAGE_PRINTING) == frozenset({
        rbac.Action.MANAGE_PRINTING, rbac.Action.MANAGE_MACHINES,
    })
    assert rbac.can(actor, rbac.Action.MANAGE_PRINTING, makerspace.id)
    assert rbac.effective_actions(actor, makerspace.id) == {
        rbac.Action.MANAGE_MACHINES, rbac.Action.MANAGE_PRINTING,
        # Also implied by MANAGE_MACHINES, so job handover comes with the machines.
        rbac.Action.COLLECT_SERVICE_REQUEST,
    }
    assert rbac.makerspaces_for_action(actor, rbac.Action.MANAGE_PRINTING) == {makerspace.id}



def test_tenant_machine_account_is_separate_from_platform_authority():
    makerspace = make_space("b5-flag-off-machine")
    platform = make_user("b5-flag-off-superadmin", role=User.Role.SUPERADMIN, access_status="active")
    staff = staff_account(makerspace, username="b5-flag-off-machine-staff", role_slug="machine_manager")
    assert rbac.can(platform, rbac.Action.MANAGE_PRINTING, makerspace.id)
    assert rbac.can(staff, rbac.Action.MANAGE_PRINTING, makerspace.id)
    assert not MakerspaceMembership.objects.filter(user=platform).exists()


def test_retirement_migration_moves_legacy_labels_without_reviving_invalid_authority():
    makerspace = make_space("b5-migrate-memberships")
    machine_role = _default_role(makerspace, MakerspaceMembership.Role.MACHINE_MANAGER)
    already = staff_account(makerspace, username="b5-migrated-default", role_slug="machine_manager")
    legacy = staff_account(makerspace, username="b5-migrated-unassigned", role_slug="machine_manager")
    handover = staff_account(makerspace, username="b5-handover", role_slug="handover")
    already_machine = MakerspaceMembership.staff_tracks.get(user=already, makerspace=makerspace)
    unassigned = MakerspaceMembership.staff_tracks.get(user=legacy, makerspace=makerspace)
    handover_membership = MakerspaceMembership.staff_tracks.get(user=handover, makerspace=makerspace)
    migration = import_module("apps.makerspaces.migrations.0046_retire_print_manager")
    # A data migration runs on HISTORICAL models, whose default manager sees every membership row.
    # Under the real models `.objects` is the member track only (U-A1), which would hide the staff
    # rows this test seeds, so hand the migration the app registry as it stood before 0046.
    from django.db.migrations.loader import MigrationLoader
    historical = MigrationLoader(connection).project_state(
        ("makerspaces", "0045_membership_join_policy_referrals")).apps
    with pytest.raises(IntegrityError), transaction.atomic():
        MakerspaceMembership.staff_tracks.filter(pk=unassigned.pk).update(assigned_role=None, role="print_manager")
        migration.migrate_print_manager_memberships(historical, None)
        migration.migrate_print_manager_memberships(historical, None)
        already_machine.refresh_from_db()
        unassigned.refresh_from_db()
        handover_membership.refresh_from_db()
        assert already_machine.assigned_role_id == machine_role.id
        assert already_machine.role == MakerspaceMembership.Role.MACHINE_MANAGER
        assert unassigned.assigned_role_id is None
        assert unassigned.role == MakerspaceMembership.Role.MACHINE_MANAGER
        assert not rbac.can(legacy, rbac.Action.MANAGE_PRINTING, makerspace.id)
        assert handover_membership.assigned_role.slug == "handover"
        assert handover_membership.role == MakerspaceMembership.Role.HANDOVER
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_invalid_legacy_print_manager_is_denied_and_historical_mutes_are_retargeted():
    makerspace = make_space("b5-legacy-and-mutes")
    legacy = staff_account(makerspace, username="b5-legacy-printer", role_slug="machine_manager")
    membership = MakerspaceMembership.staff_tracks.get(user=legacy, makerspace=makerspace)
    with pytest.raises(IntegrityError), transaction.atomic():
        MakerspaceMembership.staff_tracks.filter(pk=membership.pk).update(assigned_role=None, role="print_manager")
        assert not rbac.can(legacy, rbac.Action.MANAGE_PRINTING, makerspace.id)
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    mute = EmailNotificationMute.objects.create(
        makerspace=makerspace, target="print_manager", stream="printing", event="accepted", audience="staff",
    )
    migration = import_module("apps.integrations.migrations.0014_retire_print_manager_notification_targets")
    migration.retarget_print_manager_mutes(django_apps, None)
    mute.refresh_from_db()
    assert mute.target == "machine_manager"

