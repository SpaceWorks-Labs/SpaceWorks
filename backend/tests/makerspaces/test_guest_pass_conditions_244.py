"""Decision 244: condition matrix for the staff guest-pass desk (roles, switches, validation, replay, isolation)."""
import pytest
from django.urls import reverse

from apps.makerspaces.models import GuestPass
from apps.makerspaces.role_catalog import ROLE_BY_SLUG, ROLE_CATALOG
from tests.fixed_roles.helpers import staff_account
from tests.makerspaces.l4_helpers import features_off, features_on
from tests.makerspaces.test_guest_pass_api import _on
from tests.makerspaces.test_membership_j1 import user
from tests.return_helpers import authenticated_client, make_space

pytestmark = pytest.mark.django_db

ROLE_SLUGS = [role.slug for role in ROLE_CATALOG]


def _allowed(slug):
    """Authority is `manage_members` in the space (views_guest_passes docstring)."""
    return "manage_members" in ROLE_BY_SLUG[slug].granted_actions


@pytest.mark.parametrize("slug", ROLE_SLUGS)
def test_desk_list_and_issue_follow_manage_members_for_every_built_in_role(slug):
    makerspace = make_space(f"gpc-role-{slug}".replace("_", "-"))
    _on(makerspace)
    actor = staff_account(makerspace, f"gpc-{slug}", slug)
    guest = user(f"gpc-guest-{slug}")
    client = authenticated_client(actor)
    list_url = reverse("admin-guest-passes", args=[makerspace.pk])
    listed = client.get(list_url)
    issued = client.post(list_url, {"holder_email": guest.email}, format="json")
    if _allowed(slug):
        assert listed.status_code == 200
        assert issued.status_code == 201
        assert GuestPass.objects.filter(makerspace=makerspace, holder=guest).count() == 1
    else:
        assert listed.status_code in (403, 404)
        assert issued.status_code in (403, 404)
        assert not GuestPass.objects.filter(makerspace=makerspace).exists()


@pytest.mark.parametrize("slug", [s for s in ROLE_SLUGS if not _allowed(s)])
def test_roles_without_manage_members_cannot_revoke_or_stamp_a_waiver(slug):
    makerspace = make_space(f"gpc-rev-{slug}".replace("_", "-"))
    _on(makerspace)
    manager = staff_account(makerspace, f"gpc-rev-mgr-{slug}", "space_manager")
    guest = user(f"gpc-rev-guest-{slug}")
    created = authenticated_client(manager).post(
        reverse("admin-guest-passes", args=[makerspace.pk]), {"holder_email": guest.email}, format="json")
    pass_id = created.json()["id"]
    client = authenticated_client(staff_account(makerspace, f"gpc-rev-actor-{slug}", slug))
    for name, body in (("admin-guest-pass-revoke", {"reason": "x"}), ("admin-guest-pass-waiver", {})):
        assert client.post(reverse(name, args=[makerspace.pk, pass_id]), body, format="json").status_code in (403, 404)
    assert GuestPass.objects.get(pk=pass_id).status == "issued"


def test_desk_sale_is_404_while_only_day_passes_is_off_but_issue_still_works():
    makerspace = make_space("gpc-sale-off")
    _on(makerspace)
    features_off(makerspace, "day_passes")
    manager = authenticated_client(staff_account(makerspace, "gpc-sale-mgr", "space_manager"))
    guest = user("gpc-sale-guest")
    assert manager.post(reverse("admin-guest-pass-sale", args=[makerspace.pk]),
                        {"holder_email": guest.email, "product_id": 1}, format="json").status_code == 404
    assert manager.post(reverse("admin-guest-passes", args=[makerspace.pk]),
                        {"holder_email": guest.email}, format="json").status_code == 201


def test_every_staff_route_is_404_when_guest_passes_alone_is_off():
    makerspace = make_space("gpc-gp-off")
    _on(makerspace)
    features_off(makerspace, "guest_passes")
    manager = authenticated_client(staff_account(makerspace, "gpc-gp-off-mgr", "space_manager"))
    assert manager.get(reverse("admin-guest-passes", args=[makerspace.pk])).status_code == 404
    assert manager.post(reverse("admin-guest-passes", args=[makerspace.pk]),
                        {"holder_email": "someone@example.test"}, format="json").status_code == 404


def test_issue_validation_requires_exactly_one_holder_and_a_real_day_and_account():
    makerspace = make_space("gpc-valid")
    _on(makerspace)
    guest = user("gpc-valid-guest")
    manager = authenticated_client(staff_account(makerspace, "gpc-valid-mgr", "space_manager"))
    url = reverse("admin-guest-passes", args=[makerspace.pk])
    assert manager.post(url, {}, format="json").status_code == 400
    assert manager.post(url, {"holder_email": guest.email, "holder_id": guest.pk}, format="json").status_code == 400
    assert manager.post(url, {"holder_email": "not-an-email"}, format="json").status_code == 400
    assert manager.post(url, {"holder_email": guest.email, "day": "yesterday"}, format="json").status_code == 400
    assert manager.post(url, {"holder_email": "nobody-at-all@example.test"}, format="json").status_code == 404
    assert not GuestPass.objects.filter(makerspace=makerspace).exists()


def test_issue_with_the_same_operation_id_replays_one_pass():
    makerspace = make_space("gpc-replay")
    _on(makerspace)
    guest = user("gpc-replay-guest")
    manager = authenticated_client(staff_account(makerspace, "gpc-replay-mgr", "space_manager"))
    url = reverse("admin-guest-passes", args=[makerspace.pk])
    body = {"holder_email": guest.email, "operation_id": "gpc-op-1"}
    first, second = manager.post(url, body, format="json"), manager.post(url, body, format="json")
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert GuestPass.objects.filter(makerspace=makerspace, holder=guest).count() == 1


def test_a_pass_of_another_space_cannot_be_revoked_through_this_spaces_url():
    mine, theirs = make_space("gpc-iso-a"), make_space("gpc-iso-b")
    for space in (mine, theirs):
        _on(space)
    features_on(theirs, "guest_passes")
    other_manager = authenticated_client(staff_account(theirs, "gpc-iso-b-mgr", "space_manager"))
    guest = user("gpc-iso-guest")
    foreign = other_manager.post(reverse("admin-guest-passes", args=[theirs.pk]),
                                 {"holder_email": guest.email}, format="json").json()["id"]
    my_manager = authenticated_client(staff_account(mine, "gpc-iso-a-mgr", "space_manager"))
    assert my_manager.post(reverse("admin-guest-pass-revoke", args=[mine.pk, foreign]), {}, format="json"
                           ).status_code == 404
    assert my_manager.get(reverse("admin-guest-passes", args=[theirs.pk])).status_code in (403, 404)
    assert GuestPass.objects.get(pk=foreign).status == "issued"
