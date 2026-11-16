from tests.account_split.sweep_helpers import (
    create_test_user as _create_test_user,
)
import pytest

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.tenant_migration.tenant_dump_user_closure import build_user_closure
from apps.tenant_migration.tenant_dump_user_rows import (
    apply_user_closure,
    excluded_stub_profile_object_keys,
)


pytestmark = pytest.mark.django_db


def test_stub_profile_projects_and_exclusive_objects_are_dropped():
    space = Makerspace.objects.create(name="Profile source", slug="profile-source")
    foreign = Makerspace.objects.create(name="Profile foreign", slug="profile-foreign")
    full = _create_test_user(username="profile-full")
    stub = _create_test_user(username="profile-stub")
    full_membership = MakerspaceMembership.objects.create(
        makerspace=space,
        user=full,
        assigned_role=space.roles.get(slug="member"),
        role="custom",
    )
    stub_membership = MakerspaceMembership.objects.create(
        makerspace=space,
        user=stub,
        assigned_role=space.roles.get(slug="member"),
        role="custom",
    )
    MakerspaceMembership.objects.create(
        makerspace=foreign,
        user=stub,
        assigned_role=foreign.roles.get(slug="member"),
        role="custom",
    )
    rows = {
        "events.EventRegistration": (
            {"id": 1, "member_id": full.pk},
            {"id": 2, "member_id": stub.pk},
        ),
        "makerspaces.MakerspaceMembership": (
            {"id": full_membership.pk, "user_id": full.pk},
            {"id": stub_membership.pk, "user_id": stub.pk},
        ),
        "makerspaces.MemberProfile": (
            {"id": 10, "membership_id": full_membership.pk, "avatar_key": "full/avatar.png"},
            {"id": 11, "membership_id": stub_membership.pk, "avatar_key": "stub/avatar.png"},
        ),
        "makerspaces.MemberProject": (
            {"id": 20, "profile_id": 10, "image_key": "full/project.png"},
            {"id": 21, "profile_id": 11, "image_key": "stub/project.png"},
        ),
    }
    rows["accounts.User"] = tuple(
        User.objects.filter(pk__in=(full.pk, stub.pk)).values(
            *(field.attname for field in User._meta.concrete_fields)
        )
    )
    closure = build_user_closure(rows, space.pk, "capture-profiles")

    projected = apply_user_closure(rows, closure)
    excluded = excluded_stub_profile_object_keys(rows, projected)

    assert [row["id"] for row in projected["makerspaces.MemberProfile"]] == [10]
    assert [row["id"] for row in projected["makerspaces.MemberProject"]] == [20]
    assert excluded == {"stub/avatar.png", "stub/project.png"}
