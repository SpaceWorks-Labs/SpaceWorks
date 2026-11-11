import pytest as _pytest_stale

# STALE (R3 test phase): owner decision #63 (unified accounts) retired the separate staff
# account; d55545d7 removed apps.accounts.staff_accounts / the staff-account invitation
# mutate path. Replacement coverage: tests/admin_api/test_staff_roles_api.py.
_pytest_stale.skip("staff accounts retired by #63 (d55545d7)", allow_module_level=True)

from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError as ModelValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.account_kind_guards import RETIREMENT_GUC
from apps.accounts.models import User
from apps.accounts.staff_accounts import create_staff_account
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from .p1_helpers import sql, staff

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def context():
    root = User.objects.create_superuser("root", email="root@example.test", password="long-test-password")
    a, b = [Makerspace.objects.create(name=slug, slug=slug, created_by=root) for slug in ("create-a", "create-b")]
    return root, a, b


def test_kind_scoped_email_identity(context):
    _, a, b = context
    email = "shared@example.test"
    member = User.objects.create_user("member", email=email)
    first, _ = staff(a, "a", email=email)
    second, _ = staff(b, "b", email=email)
    platform = User.objects.create_superuser("operator", email=email)
    assert len({member.pk, first.pk, second.pk, platform.pk}) == 4
    with pytest.raises(IntegrityError):
        staff(a, "a-duplicate", email=email.upper())
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user("member-duplicate", email=email.upper())
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_superuser("operator-duplicate", email=email.upper())


@pytest.mark.parametrize("field,value", [("phone_e164", "+14155552671"), ("telegram_user_id", "12345")])
def test_member_only_identity_uniqueness(context, field, value):
    _, a, _ = context
    User.objects.create_user("member", **{field: value})
    staff(a, "staff-a", **{field: value})
    staff(a, "staff-b", **{field: value})
    User.objects.create_superuser("operator", **{field: value})
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user("duplicate", **{field: value})


def test_empty_identities_and_global_username(context):
    _, a, _ = context
    for index in range(2):
        User.objects.create_user(f"member-{index}")
        staff(a, f"staff-{index}")
        User.objects.create_superuser(f"platform-{index}")
    with pytest.raises(IntegrityError), transaction.atomic():
        staff(a, "member-0")


def test_manager_rejects_inconsistent_flags_and_context(context):
    _, a, _ = context
    assert User.objects.create_user("member").account_kind == "member"
    assert User.objects.create_superuser("operator").account_kind == "platform"
    for options in (
        {"is_superuser": True}, {"role": "superadmin"}, {"account_kind": "staff"},
        {"staff_makerspace": a}, {"account_kind": "unknown"},
        {"account_kind": "platform", "is_superuser": False},
    ):
        with pytest.raises(ValueError): User.objects.create_user("invalid", **options)
    with pytest.raises(ValueError): User.objects.create_superuser("invalid", account_kind="member")


def test_staff_service_atomic_complete_set_and_audit(context, monkeypatch):
    from apps.machines.models import MachineType
    root, a, _ = context
    machine_type = MachineType.objects.create(
        makerspace=a, slug="test-machine", name="Test machine", is_builtin=False,
    )
    quotas = []
    monkeypatch.setattr("apps.accounts.staff_accounts.limits.check_quota", lambda space, resource, adding: quotas.append((space.pk, resource, adding)))
    user = create_staff_account(a, name="Alex Maker", email="Alex@Example.test", username="alex",
        roles=[a.roles.get(slug="machine_manager"), a.roles.get(slug="inventory_manager")],
        machine_type_ids=[machine_type.pk], created_by=root)
    assert user.account_kind == "staff" and user.staff_makerspace_id == a.pk
    assert user.username == "alex.create-a" and user.email == "alex@example.test"
    assert user.display_name == "Alex Maker" and not user.has_usable_password() and user.must_change_password
    assert user.credential_generation == 0
    membership = user.makerspace_memberships.get()
    assert membership.assigned_role.slug == "inventory_manager"
    assert list(membership.additional_roles.values_list("role__slug", flat=True)) == ["machine_manager"]
    assert list(membership.machine_type_scopes.values_list("machine_type_id", flat=True)) == [machine_type.pk]
    assert (a.pk, "staff", 1) in quotas
    assert AuditLog.objects.filter(action="staff.account_created", target_id=str(user.pk), makerspace=a).exists()
    captured = user.username
    a.slug = "renamed"
    a.save(update_fields=["slug"])
    user.refresh_from_db()
    assert user.username == captured


@pytest.mark.parametrize("overrides", [
    {"name": ""}, {"email": "invalid"}, {"username": "spaces forbidden"}, {"roles": []},
    {"machine_type_ids": [True]}, {"machine_type_ids": [1, 1]}, {"machine_type_ids": [999999]},
])
def test_service_validation_rolls_back_principal_and_membership(context, overrides):
    root, a, _ = context
    before = User.objects.count()
    values = dict(name="Valid", email="valid@example.test", username="valid",
                  roles=[a.roles.get(slug="machine_manager")], machine_type_ids=[], created_by=root)
    values.update(overrides)
    with pytest.raises(ValidationError): create_staff_account(a, **values)
    assert User.objects.count() == before


def test_member_role_foreign_role_and_unprivileged_creator_refused(context):
    root, a, b = context
    member = User.objects.create_user("community")
    for roles in ([a.roles.get(slug="member")], [b.roles.get(slug="inventory_manager")],
                  [a.roles.get(slug="space_manager"), a.roles.get(slug="handover")]):
        with pytest.raises(ValidationError):
            create_staff_account(a, name="Invalid", roles=roles, created_by=root)
    with pytest.raises(PermissionDenied):
        create_staff_account(a, name="Invalid", roles=[a.roles.get(slug="handover")], created_by=member)
    manager, _ = staff(a, "manager", role="space_manager")
    with pytest.raises(PermissionDenied):
        create_staff_account(a, name="Invalid", roles=[a.roles.get(slug="space_manager")], created_by=manager)
    assert create_staff_account(a, name="Valid", roles=[a.roles.get(slug="handover")], created_by=manager)


def test_staff_username_collisions_and_typed_email_conflict(context):
    root, a, _ = context
    role = a.roles.get(slug="handover")
    first = create_staff_account(a, name="Alex", username="alex", email="one@example.test", roles=[role], created_by=root)
    second = create_staff_account(a, name="Alex", username="alex", email="two@example.test", roles=[role], created_by=root)
    assert first.username == "alex.create-a" and second.username != first.username
    assert second.username.startswith("alex-") and second.username.endswith(".create-a")
    before = User.objects.count()
    with pytest.raises(ValidationError) as error:
        create_staff_account(a, name="Another", email="ONE@example.test", roles=[role], created_by=root)
    assert "email" in error.value.detail and User.objects.count() == before


def test_model_immutability_including_deferred_loads(context):
    _, a, b = context
    user, membership = staff(a)
    deferred = User.objects.only("id").get(pk=user.pk)
    deferred.staff_makerspace = b
    with pytest.raises(ModelValidationError): deferred.save(update_fields=["staff_makerspace"])
    user.account_kind = "member"
    with pytest.raises(ModelValidationError): user.save()
    user.refresh_from_db()
    with transaction.atomic():
        sql("SELECT set_config(%s,%s,true)", [RETIREMENT_GUC, str(a.pk)])
        membership.delete()
        user.staff_makerspace, user.retired_at, user.is_active = None, timezone.now(), False
        user.save()
    user.retired_at = None
    with pytest.raises(ModelValidationError): user.save()


def test_setup_instance_declares_platform_and_refuses_promotion(settings):
    settings.SETUP_ORGANIZATION_NAME = "Operator"
    call_command("setup_instance", username="operator", email="operator@example.test", password="test-password",
                 makerspace_name="Setup", makerspace_slug="setup")
    assert User.objects.get(username="operator").account_kind == "platform"
    User.objects.create_user("community")
    with pytest.raises(CommandError):
        call_command("setup_instance", username="community", password="test-password", makerspace_slug="setup")


def test_restore_superadmin_does_not_adopt_member_with_same_email(context):
    from apps.backup.models import DeploymentRecoveryState
    from apps.tenant_migration.tenant_restore_superadmin import create_target_superadmin
    import uuid
    User.objects.create_user("community", email="restore@example.test")
    DeploymentRecoveryState.objects.update_or_create(pk=1, defaults={"mode": "target_import"})
    store = SimpleNamespace(get_or_prepare=lambda **kw: {"secret": "test-password"})
    user = create_target_superadmin(email="restore@example.test", run_id=uuid.uuid4(),
                                   artifact_sha256="a" * 64, delivery_store=store)
    assert user.account_kind == "platform" and user.is_superuser and user.role == "superadmin"
