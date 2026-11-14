from datetime import datetime, timezone as dt_timezone

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.makerspaces.models import Makerspace
from apps.makerspaces.profile_services import save_profile
from apps.makerspaces.public_profile_handles import claim_handle
from apps.makerspaces.public_profile_reserved import RESERVED_SEGMENTS

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("viewer", ["anonymous", "owner", "other"])
def test_public_profile_card_is_viewer_independent_and_is_never_cached(world, viewer):
    membership = world.owner.makerspace_memberships.get(makerspace=world.space)
    membership.activated_at = datetime(2025, 1, 2, 12, tzinfo=dt_timezone.utc)
    membership.save(update_fields=["activated_at"])
    world.space.enabled_modules = sorted(set(world.space.enabled_modules) | {"member_accounts", "membership"})
    world.space.timezone = "UTC"
    world.space.save(update_fields=["enabled_modules", "timezone"])
    save_profile(membership, {"bio": "Builds useful things"})
    claim = claim_handle(membership.user, "wire.maker")
    user = {"anonymous": None, "owner": world.owner, "other": world.other}[viewer]
    response = world.client(user, jwt=bool(user)).get(reverse("public-profile", kwargs={"handle": claim.handle}))
    assert response.status_code == 200, response.data
    # Decision 549: anonymous and real JWT viewers receive the same allow-listed public card.
    assert response.data == {
        "display_name": "wire-owner", "avatar_url": None, "handle": "wire.maker",
        "bio": "Builds useful things", "projects": [],
        "memberships": [{"slug": "p3-wire", "name": "Wire lab", "role_title": "Member", "started_on": "2025-01-02"}],
    }
    assert {"audience", "viewer_is_owner", "verified", "id", "user_id", "membership_id",
            "email", "phone", "address", "loans", "payments", "evidence", "audit",
            "public_visible", "public_consented_at", "public_reconfirm_pending"}.isdisjoint(response.data)
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
