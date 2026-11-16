import pytest
from django.db.models import UniqueConstraint
from django.forms import modelform_factory

from apps.accounts.admin_account_forms import AccountUserChangeForm, PlatformUserCreationForm
from apps.accounts.models import User
from apps.backup.main_projection_registry import (
    BoundaryDisposition, INERT_SHELL_BOUNDARIES, _boundary_disposition, table_rules,
)
from apps.data_export.fields import FIELDS
from apps.data_export.types import Fidelity, Omitted
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.tenant_migration.unique_values import USER_IDENTITY_UNIQUE_RULES
from .p1_helpers import staff

pytestmark = pytest.mark.django_db


def test_user_unique_registry_has_exact_constraint_coverage():
    constraints = {constraint.name for constraint in User._meta.constraints if isinstance(constraint, UniqueConstraint)}
    assert set(USER_IDENTITY_UNIQUE_RULES) == {"username", *constraints}


def test_new_fields_have_explicit_export_dispositions():
    for fidelity in Fidelity:
        # Stale after 2f8cf73c (C-18, PORTABLE format 2): one account per person, so the users
        # projection drops the always-empty staff_makerspace; staff roles travel as staff-track rows.
        assert isinstance(FIELDS[(fidelity, "accounts.User", "staff_makerspace")], Omitted)
        assert isinstance(FIELDS[(fidelity, "accounts.User", "credential_generation")], Omitted)
        assert isinstance(FIELDS[(fidelity, "accounts.User", "retired_at")], Omitted)


def test_staff_backup_boundary_is_inert_shell_never_drop_or_null():
    assert ("accounts.User", "staff_makerspace") in INERT_SHELL_BOUNDARIES
    rule = next(rule for rule in table_rules() if rule.model is User)
    assert _boundary_disposition(rule, User._meta.get_field("staff_makerspace")) == BoundaryDisposition.INERT_SHELL_TO_SLICE


def test_control_creation_form_declares_platform():
    form = PlatformUserCreationForm(data={"username": "operator", "password1": "Strong-test-password-123!",
        "password2": "Strong-test-password-123!", "usable_password": "true"})
    assert form.is_valid(), form.errors
    user = form.save()
    assert user.account_kind == "platform" and user.is_superuser and user.is_staff and user.role == "superadmin"


@pytest.mark.parametrize("kind", ["member", "staff"])
def test_control_form_refuses_promoting_an_existing_account(kind):
    space = Makerspace.objects.create(name="Admin", slug="admin")
    user = staff(space)[0] if kind == "staff" else User.objects.create_user("member")
    Form = modelform_factory(User, form=AccountUserChangeForm,
                             fields=["username", "role", "is_superuser", "is_staff"])
    form = Form(instance=user, data={"username": user.username, "role": "superadmin",
                                    "is_superuser": True, "is_staff": True})
    assert not form.is_valid()
    assert "separate platform account" in str(form.errors)


def test_recovery_refuses_nonplatform_even_before_password_write():
    from apps.backup.recovery import set_recovery_principal
    from rest_framework.exceptions import ValidationError
    member = User.objects.create_user("member")
    old = member.password
    with pytest.raises(ValidationError): set_recovery_principal(member, "new-secret")
    member.refresh_from_db()
    assert member.password == old


def test_staff_quota_excludes_community_members():
    from apps.makerspaces.limits_usage import _members, _staff
    space = Makerspace.objects.create(name="Quota", slug="quota")
    member = User.objects.create_user("community")
    MakerspaceMembership.objects.create(user=member, makerspace=space, role="custom", assigned_role=space.roles.get(slug="member"))
    staff(space)
    assert _staff(space) == 1 and _members(space) == 1
