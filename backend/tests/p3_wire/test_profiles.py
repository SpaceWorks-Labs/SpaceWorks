import pytest
from django.urls import reverse
from django.utils import timezone

from apps.makerspaces.models import Makerspace
from apps.makerspaces.profile_services import save_profile
from apps.makerspaces.public_profile_handles import claim_handle
from apps.makerspaces.public_profile_reserved import RESERVED_SEGMENTS

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("viewer", ["anonymous", "owner", "other"])
def test_public_profile_owner_flag_uses_authenticated_identity_and_is_never_cached(world, viewer):
    membership = world.owner.makerspace_memberships.get(makerspace=world.space)
    save_profile(membership, {"public_visible": True, "publication_consent": True})
    claim = claim_handle(membership.user, "wire.maker")
    user = {"anonymous": None, "owner": world.owner, "other": world.other}[viewer]
    response = world.client(user, jwt=bool(user)).get(reverse("public-profile", kwargs={"handle": claim.handle}))
    assert response.status_code == 200, response.data
    assert response.data["audience"] == {"anonymous": "public", "owner": "owner", "other": "member"}[viewer]
    assert response["Cache-Control"] == "no-store"


def test_profile_preview_verification_comes_from_selected_membership(world):
    own = world.owner.makerspace_memberships.get(makerspace=world.space)
    other_space = Makerspace.objects.create(name="Other profile", slug="wire-profile-other")
    from apps.makerspaces.models import MakerspaceMembership
    MakerspaceMembership.objects.create(makerspace=other_space, user=world.owner, role="custom",
        assigned_role=other_space.roles.get(slug="member"), verified_at=timezone.now())
    url = reverse("member-profile", kwargs={"makerspace_id": world.space.pk})
    client = world.client(world.owner, jwt=True)
    response = client.get(url)
    assert response.status_code == 200, response.data
    assert response.data["verified"] is False
    own.verified_at = timezone.now()
    own.save(update_fields=["verified_at"])
    assert client.get(url).data["verified"] is True
    assert client.patch(url, {"headline": "Maker"}, format="json").data["verified"] is True


def test_now_stays_reserved():
    assert "now" in RESERVED_SEGMENTS
