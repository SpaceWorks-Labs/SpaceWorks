from tests.account_split.sweep_helpers import (
    create_test_user as _create_test_user,
)
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.makerspaces.models import Makerspace, MakerspaceMembership


pytestmark = pytest.mark.django_db


def create_user(username="admin", **overrides):
    defaults = {
        "email": f"{username}@example.com",
    }
    defaults.update(overrides)
    return _create_test_user(username=username, **defaults)


def create_makerspace():
    return Makerspace.objects.create(name="Main Lab", slug="main-lab")


def test_membership_links_reverse_relations_with_member_role():
    user = create_user()
    makerspace = create_makerspace()

    membership = MakerspaceMembership.objects.create(
        makerspace=makerspace,
        user=user,
        role="custom", assigned_role=makerspace.roles.get(slug="member"),
    )

    assert membership.assigned_role.slug == "member"
    assert user.makerspace_memberships.get() == membership
    assert makerspace.memberships.get() == membership


def test_duplicate_makerspace_user_membership_raises_integrity_error():
    user = create_user()
    makerspace = create_makerspace()
    MakerspaceMembership.objects.create(
        makerspace=makerspace, user=user, role="custom",
        assigned_role=makerspace.roles.get(slug="member"),
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        MakerspaceMembership.objects.create(
            makerspace=makerspace, user=user, role="custom",
            assigned_role=makerspace.roles.get(slug="member"),
        )


def test_clean_rejects_inactive_user():
    user = create_user(is_active=False)
    makerspace = create_makerspace()
    membership = MakerspaceMembership(makerspace=makerspace, user=user)

    with pytest.raises(ValidationError):
        membership.clean()


def test_clean_allows_unset_user():
    makerspace = create_makerspace()
    # No user assigned yet (e.g. an empty inline row) — clean() must not raise.
    MakerspaceMembership(makerspace=makerspace).clean()
