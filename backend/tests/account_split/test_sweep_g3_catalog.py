"""Account split coverage for the Lane D field and staff transport catalogs."""

import pytest
from django.apps import apps

from apps.accounts.models import StaffInvitation, User
from apps.backup.main_projection_registry import INERT_SHELL_BOUNDARIES
from apps.backup.raw_projection import raw_records
from apps.machines.models import MachineType
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.notifications.models import MemberNotificationPreference
from apps.tenant_migration.tenant_dump_builder import _sanitize_rows
from apps.tenant_migration.tenant_dump_catalog import FIELD_POLICIES, validate_field_coverage
from apps.tenant_migration.tenant_dump_field_snapshot import FIRST_PARTY_FIELD_NAMES
from apps.tenant_migration.tenant_dump_raw import RAW_COLUMN_ALLOWLISTS
from apps.tenant_migration.tenant_dump_staff import prepare_staff_rows, remap_account_roles
from apps.tenant_migration.tenant_dump_types import AuthorityDisposition as D
from apps.tenant_migration.tenant_dump_user_closure import build_user_closure
from apps.tenant_migration.tenant_dump_user_rows import _stub_values, apply_user_closure
from tests.accounts.account_factories import make_membership, make_staff
from tests.fixed_roles.helpers import assign_builtin_roles


def test_account_fields_have_reviewed_raw_and_authority_classification():
    models = (User, StaffInvitation)
    policies = {edge: rule for edge, rule in FIELD_POLICIES.items()
                if edge[0] in {model._meta.label for model in models}}
    validate_field_coverage(models, policies)
    assert {'account_kind', 'staff_makerspace', 'retired_at', 'credential_generation'} <= FIRST_PARTY_FIELD_NAMES['accounts.User']
    assert 'staff_makerspace_id' in RAW_COLUMN_ALLOWLISTS['accounts.User']
    assert 'account_id' in RAW_COLUMN_ALLOWLISTS['accounts.StaffInvitation']
    assert FIELD_POLICIES['accounts.User', 'credential_generation'].dispositions == (D.RESET,)
    assert FIELD_POLICIES['accounts.StaffInvitation', 'account'].dispositions == (D.DROP,)
    assert ('accounts.User', 'staff_makerspace') in INERT_SHELL_BOUNDARIES


@pytest.mark.django_db
def test_staff_roles_scopes_preferences_and_identity_travel_without_credentials():
    space = Makerspace.objects.create(name='Staff transport', slug='staff-transport')
    kind = MachineType.objects.create(makerspace=space, name='Laser', slug='transport-laser')
    staff = make_staff(space, username='transport-staff', role_slug='machine_manager',
                       password='Source password 947!', credential_generation=19)
    assign_builtin_roles(staff, space, 'machine_manager', 'handover', machine_types=[kind])
    # Stale after U-A1 + 11c64a43/2f8cf73c (C-18): one account per person -- the staff role is a
    # staff-TRACK row (not on the default community manager), the capture reads every track, the
    # staff_makerspace edge and the staff password reset are gone (a full person keeps its hash).
    membership = MakerspaceMembership.staff_tracks.get(user=staff)
    membership.receives_notifications = False
    membership.save(update_fields=['receives_notifications'])
    member = User.objects.create_user(username='transport-member')
    make_membership(member, space)
    for user in (staff, member):
        MemberNotificationPreference.objects.create(makerspace=space, user=user,
            feature='maintenance', channel='email', enabled=False, daily_digest=True)
    labels = ('accounts.User', 'makerspaces.MakerspaceMembership',
              'makerspaces.MembershipAdditionalRole', 'machines.MembershipMachineTypeScope',
              'notifications.MemberNotificationPreference')
    rows = {label: tuple(raw_records(apps.get_model(label)._base_manager.all(), apps.get_model(label)))
            for label in labels}
    prepared = prepare_staff_rows(rows, space.pk, using='default')
    closure = build_user_closure(prepared, space.pk, 'staff-capture')
    carried = apply_user_closure(prepared, closure)
    users = {row['id']: row for row in carried['accounts.User']}
    assert users[staff.pk]['staff_makerspace_id'] is None
    assert users[staff.pk]['password'] == staff.password
    assert users[staff.pk]['is_staff'] is False and users[staff.pk]['is_superuser'] is False
    assert [row['user_id'] for row in carried['notifications.MemberNotificationPreference']] == [staff.pk]
    role_ids = {role.slug: role.pk + 10000 for role in space.roles.all()}
    projected = remap_account_roles(_sanitize_rows(carried, space.pk), role_ids, carried)
    by_label = {}
    for row in projected:
        by_label.setdefault(row.model._meta.label, []).append(row.values)
    # Credential generations are source-local proof state: RESET in the sanitized projection.
    assert next(row for row in by_label['accounts.User'] if row['id'] == staff.pk)['credential_generation'] == 0
    staff_row = next(row for row in by_label['makerspaces.MakerspaceMembership'] if row['user_id'] == staff.pk)
    member_row = next(row for row in by_label['makerspaces.MakerspaceMembership'] if row['user_id'] == member.pk)
    assert staff_row['assigned_role_id'] == role_ids['machine_manager']
    assert staff_row['role'] == 'machine_manager'
    assert staff_row['receives_notifications'] is False
    assert member_row['assigned_role_id'] == role_ids['member'] and member_row['role'] == 'custom'
    assert by_label['makerspaces.MembershipAdditionalRole'][0]['role_id'] == role_ids['handover']
    assert by_label['machines.MembershipMachineTypeScope'][0]['machine_type_id'] == kind.pk
    assert by_label['notifications.MemberNotificationPreference'][0]['daily_digest'] is True


def test_foreign_or_platform_provenance_stub_cannot_carry_account_authority():
    values = _stub_values('artifact-reference')
    assert values['account_kind'] == 'member' and values['staff_makerspace_id'] is None
    assert values['retired_at'] is None and values['credential_generation'] == 0
    assert values['password'].startswith('!') and values['is_active'] is False
    assert values['is_superuser'] is False and values['is_staff'] is False
