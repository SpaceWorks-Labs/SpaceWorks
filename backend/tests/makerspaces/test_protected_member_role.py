"""The built-in Member stays action-less and remains the community join role."""
import pytest

from apps.makerspaces import membership_services
from apps.makerspaces.models import Makerspace, MakerspaceRole, MakerspaceMembership
from apps.makerspaces.roles import ensure_default_roles
from tests.makerspaces.test_membership_j1 import space, user

pytestmark = pytest.mark.django_db


def test_member_canonicalization_preserves_identity_and_joining():
    makerspace = space("member-protected", membership_policy=Makerspace.MembershipPolicy.OPEN)
    role = MakerspaceRole.objects.get(makerspace=makerspace, slug="member")
    MakerspaceRole.objects.filter(pk=role.pk).update(name="Changed", granted_actions=["view_inventory"])
    ensure_default_roles(makerspace)
    role.refresh_from_db()
    assert (role.name, role.slug, role.granted_actions) == ("Member", "member", [])
    assert role.is_default and role.is_protected
    joiner = user("member-protected-joiner")
    assert membership_services.request_membership(joiner, makerspace)["outcome"] == "joined"
    assert MakerspaceMembership.objects.get(user=joiner, makerspace=makerspace).assigned_role_id == role.pk
