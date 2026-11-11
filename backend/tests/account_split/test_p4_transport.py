from uuid import uuid4

import pytest

from apps.accounts.models import User, UserMFA
from apps.machines.models import MachineType, MembershipMachineTypeScope
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MembershipAdditionalRole
from apps.notifications.models import MemberNotificationPreference
from apps.notifications.models_preferences import NotificationPreference
from apps.tenant_migration.materialization import materialize_tenant
from apps.tenant_migration.tenant_dump_source_projection import project_makerspace_source
from tests.data_export.portable_helpers import make_space, make_user
from tests.encryption.conftest import enabled_encryption
from tests.tenant_migration.materialization_helpers import portable_import_case
from .p1_helpers import staff

pytestmark = pytest.mark.django_db(transaction=True)


def authority(space):
    user, membership = staff(space, "transport-staff", email="shared@example.test", display_name="Staff Identity",
                             phone="+15551234567")
    membership.receives_notifications = False
    membership.save(update_fields=["receives_notifications"])
    MembershipAdditionalRole.objects.create(membership=membership, role=space.roles.get(slug="machine_manager"))
    machine_type = MachineType.objects.create(makerspace=space, name="Custom Type", slug="staff-custom")
    MembershipMachineTypeScope.objects.create(membership=membership, machine_type=machine_type)
    MemberNotificationPreference.objects.create(makerspace=space, user=user,
        feature="hardware_requests", channel="email", enabled=False, daily_digest=True)
    NotificationPreference.objects.create(makerspace=space, user=user, category="hardware_requests",
        channels=["telegram", "email"], email_fallback=False)
    user.set_password("Source-password-0123")
    user.save(update_fields=["password"])
    UserMFA.objects.create(user=user, secret="source-mfa-secret")
    return user, membership, machine_type


def assert_staff_target(user, space):
    assert user.account_kind == "staff" and user.staff_makerspace_id == space.pk
    assert user.email == "shared@example.test" and user.phone == "+15551234567"
    assert not user.has_usable_password() and user.must_change_password
    assert not UserMFA.objects.filter(user=user).exists()
    membership = MakerspaceMembership.objects.get(user=user)
    assert membership.assigned_role == space.roles.get(slug="inventory_manager")
    assert membership.receives_notifications is False
    assert set(membership.additional_roles.values_list("role__slug", flat=True)) == {"machine_manager"}
    scopes = MembershipMachineTypeScope.objects.filter(membership=membership)
    assert list(scopes.values_list("machine_type__slug", flat=True)) == ["staff-custom"]
    assert scopes.get().machine_type.makerspace_id == space.pk
    preference = MemberNotificationPreference.objects.get(makerspace=space, user=user)
    assert preference.enabled is False and preference.daily_digest is True
    personal = NotificationPreference.objects.get(makerspace=space, user=user)
    assert personal.channels == ["telegram", "email"] and personal.email_fallback is False


def test_portable_roundtrip_preserves_staff_authority_without_source_credentials():
    with enabled_encryption():
        source = make_space("p4-portable")
        member = make_user("p4-portable-member")
        source_staff, _, source_type = authority(source)
        with portable_import_case(source, member) as case:
            case.decide_walk_in(member)
            case.decide_walk_in(source_staff)
            result = materialize_tenant(case.root, case.job, case.carried,
                target_identity={"slug": "p4-portable-target"})
        target = Makerspace.objects.get(pk=result.target_makerspace_id)
        imported = User.objects.get(account_kind="staff", staff_makerspace=target)
        assert imported.pk != source_staff.pk
        assert_staff_target(imported, target)
        target_member = MakerspaceMembership.objects.get(makerspace=target, user__account_kind="member")
        assert target_member.assigned_role == target.roles.get(slug="member")
        assert not target_member.additional_roles.exists()
        assert MembershipMachineTypeScope.objects.get(membership__user=imported).machine_type_id != source_type.pk
        source_staff.refresh_from_db()
        assert source_staff.check_password("Source-password-0123")


def test_sovereign_dump_roundtrip_retains_staff_and_inert_platform_provenance(
    tmp_path, allow_projection_databases,
):
    from apps.backup.projection_databases import temporary_database, restore_dump
    from apps.tenant_migration.tenant_dump_builder import build_tenant_dump
    source = make_space("p4-sovereign")
    source_staff, _, _ = authority(source)
    capture = uuid4()
    projection = project_makerspace_source(source.pk, capture_id=capture)
    emitted = next(row for row in projection.rows["accounts.User"] if row["id"] == source_staff.pk)
    assert emitted["account_kind"] == "staff" and emitted["password"].startswith("!")
    result = build_tenant_dump(projection, tmp_path / "staff.dump", run_id=capture, source_pii_mode="plaintext")
    with temporary_database("p4_staff_transport") as (using, database_name):
        restore_dump(result.database_dump, database_name)
        target = User.objects.using(using).get(pk=source_staff.pk)
        assert target.account_kind == "staff" and target.staff_makerspace_id == source.pk
        assert not target.has_usable_password() and target.must_change_password
        assert not UserMFA.objects.using(using).filter(user_id=target.pk).exists()
        membership = MakerspaceMembership.objects.using(using).get(user_id=target.pk)
        assert membership.assigned_role_id != source.roles.get(slug="member").pk
        assert MembershipAdditionalRole.objects.using(using).filter(membership=membership).count() == 1
        assert MembershipMachineTypeScope.objects.using(using).filter(membership=membership).count() == 1
