"""Membership activation creates the per-space reference token eagerly, idempotently (decision 305)."""
import pytest

from apps.accounts.models import User
from apps.makerspaces.account_profile import ensure_legacy_pointer, ensure_legacy_pointers
from apps.makerspaces.membership_activation import _activate_membership
from apps.makerspaces.models import AccountProfile, MakerspaceMembership, MakerspaceRole, MemberProfile

from .conftest import make_person

pytestmark = pytest.mark.django_db


def activate(space, user, source="approval"):
    role = MakerspaceRole.objects.get(makerspace=space, slug="member")
    return _activate_membership(user, space, user, role, source=source)


def test_activation_creates_the_token_immediately_and_reactivation_does_not_duplicate(space_a):
    user = make_person("fresh-member")
    activate(space_a, user)
    membership = MakerspaceMembership.all_tracks.get(user=user, makerspace=space_a)
    assert MemberProfile.objects.filter(membership=membership).count() == 1
    MakerspaceMembership.all_tracks.filter(pk=membership.pk).update(status="revoked")
    activate(space_a, user)  # reactivation
    assert MemberProfile.objects.filter(membership=membership).count() == 1


def test_token_inherits_the_account_avatar_and_helpers_are_idempotent(space_a):
    user = make_person("avatar-member")
    AccountProfile.objects.create(user=user, avatar_key=f"member/{space_a.pk}/me.png")
    activate(space_a, user)
    membership = MakerspaceMembership.all_tracks.get(user=user, makerspace=space_a)
    assert MemberProfile.objects.get(membership=membership).avatar_key.endswith("me.png")
    first = ensure_legacy_pointer(membership)
    ensure_legacy_pointers(user)
    assert ensure_legacy_pointer(membership).pk == first.pk
    assert MemberProfile.objects.filter(membership=membership).count() == 1
    assert User.objects.filter(pk=user.pk).exists()
