"""U-A2: password recovery is for a person or the platform superadmin only."""

import pytest

from apps.accounts.models import User
from apps.accounts.password_reset_context import recoverable, resolve_account
from apps.accounts.serializers_password_reset import ForgotPasswordRequestSerializer
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import make_staff

pytestmark = pytest.mark.django_db


def test_context_is_person_or_platform_only():
    for value, stored in (("person", "member"), ("member", "member"), ("platform", "platform")):
        serializer = ForgotPasswordRequestSerializer(data={"context": value, "email": "a@b.test"})
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["context"] == stored
    default = ForgotPasswordRequestSerializer(data={"email": "a@b.test"})
    assert default.is_valid() and default.validated_data["context"] == "member"
    staff = ForgotPasswordRequestSerializer(data={"context": "staff", "makerspace": "x", "email": "a@b.test"})
    assert not staff.is_valid()


def test_a_converted_staff_person_recovers_through_the_person_context():
    space = Makerspace.objects.create(name="Recovery", slug="recovery-space")
    staff = make_staff(space, username="recovery-staff", email="staff@recovery.test")
    assert resolve_account("staff@recovery.test", context="member") == staff
    assert recoverable(staff, context="member")
    assert resolve_account("staff@recovery.test", context="staff", makerspace=space.slug) is None
    assert not recoverable(staff, context="staff")


def test_platform_recovery_needs_a_platform_origin(settings):
    root = User.objects.create_superuser("recovery-root", email="root@recovery.test", password="x" * 20)
    assert resolve_account("recovery-root", context="platform") == root
    assert resolve_account("root@recovery.test", context="member") is None
    assert recoverable(root, context="platform", origin=settings.PLATFORM_STAFF_ORIGINS[0])
    assert not recoverable(root, context="platform", origin="https://elsewhere.test")
