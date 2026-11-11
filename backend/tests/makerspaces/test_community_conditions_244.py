"""Decision 244: role, switch, validation and isolation matrix for the staff community routes (minors, policy)."""
import pytest
from rest_framework.test import APIClient

from apps.makerspaces.models import MinorProfile
from apps.makerspaces.role_catalog import ROLE_BY_SLUG, ROLE_CATALOG
from tests.fixed_roles.helpers import staff_account
from tests.makerspaces.l4_helpers import features_off, features_on
from tests.makerspaces.test_membership_j1 import space

pytestmark = pytest.mark.django_db(transaction=True)
SLUGS = [role.slug for role in ROLE_CATALOG]


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _ready(slug):
    makerspace = space(slug)
    makerspace.enabled_modules = sorted(set(makerspace.enabled_modules or []) | {"membership"})
    makerspace.save(update_fields=["enabled_modules"])
    features_on(makerspace, "minors")
    return makerspace


@pytest.mark.parametrize("slug", SLUGS)
def test_minors_list_and_policy_follow_the_actions_each_built_in_role_holds(slug):
    makerspace = _ready(f"comm-role-{slug}".replace("_", "-"))
    client = _client(staff_account(makerspace, f"comm-actor-{slug}", slug))
    granted = ROLE_BY_SLUG[slug].granted_actions
    minors_list = client.get(f"/api/v1/admin/makerspaces/{makerspace.pk}/minors")
    policy = client.get(f"/api/v1/admin/makerspaces/{makerspace.pk}/community-policy")
    assert (minors_list.status_code == 200) is ("manage_members" in granted)
    assert (policy.status_code == 200) is ("manage_makerspace" in granted)
    for refused in (r for r in (minors_list, policy) if r.status_code != 200):
        assert refused.status_code in (403, 404)


def test_policy_and_minors_routes_disappear_when_their_switch_is_off():
    makerspace = _ready("comm-off")
    boss = _client(staff_account(makerspace, "comm-off-boss", "space_manager"))
    base = f"/api/v1/admin/makerspaces/{makerspace.pk}"
    assert boss.get(f"{base}/minors").status_code == 200
    features_off(makerspace, "minors")
    assert boss.get(f"{base}/minors").status_code == 404
    assert boss.get(f"{base}/guardian-terms").status_code == 404
    makerspace.refresh_from_db()
    makerspace.enabled_modules = [m for m in makerspace.enabled_modules if m != "membership"]
    makerspace.save(update_fields=["enabled_modules"])
    assert boss.get(f"{base}/community-policy").status_code in (403, 404)


def test_policy_patch_validates_and_is_refused_for_a_plain_manager_of_another_space():
    mine, theirs = _ready("comm-pol-a"), _ready("comm-pol-b")
    boss = _client(staff_account(mine, "comm-pol-a-boss", "space_manager"))
    url = f"/api/v1/admin/makerspaces/{mine.pk}/community-policy"
    assert boss.patch(url, {"minors_minimum_age": "not-a-number"}, format="json").status_code == 400
    assert boss.patch(f"/api/v1/admin/makerspaces/{theirs.pk}/community-policy", {"minors_minimum_age": 14},
                      format="json").status_code in (403, 404)
    assert boss.get(url).json()["minors_minimum_age"] == 13  # the default survived both refusals


def test_a_minor_profile_of_another_space_cannot_be_cleared_through_this_spaces_url():
    mine, theirs = _ready("comm-iso-a"), _ready("comm-iso-b")
    boss = _client(staff_account(mine, "comm-iso-a-boss", "space_manager"))
    from tests.makerspaces.test_membership_j1 import user
    child = user("comm-iso-child")
    from apps.makerspaces import minors
    from apps.makerspaces.models import CommunityPolicy
    CommunityPolicy.objects.create(makerspace=theirs, minors_admitted=True)
    their_staff = staff_account(theirs, "comm-iso-b-boss", "space_manager")
    minors.publish_terms(their_staff, theirs, "I consent.", "v1")
    profile = minors.record_minor(their_staff, theirs, child, date_of_birth="2012-01-01")
    response = boss.post(f"/api/v1/admin/makerspaces/{mine.pk}/minors/{profile.pk}/clear", {}, format="json")
    assert response.status_code == 404
    assert MinorProfile.objects.filter(pk=profile.pk).exists()
