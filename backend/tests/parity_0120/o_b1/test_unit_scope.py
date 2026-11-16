"""O-B1: unit scope narrows local staff authority only -- roster, requests, per-row 404, wide settings, off."""
import pytest
from django.urls import reverse

from apps.accounts import rbac
from apps.makerspaces import member_unit_assign as assign
from apps.makerspaces import member_unit_scope as scope
from apps.makerspaces.membership_join_units import record_request_unit
from apps.makerspaces.models import MembershipRequest
from tests.makerspaces.l4_helpers import features_off
from tests.parity_0120.o_b1.helpers import community_member, lead, tree, units_space
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db(transaction=True)


def _setup(slug):
    space, boss = units_space(slug)
    south, kochi, north = tree(boss, space)
    inside, outside, nowhere = (community_member(space, f"{slug}-{n}") for n in ("in", "out", "none"))
    assign.assign_member_unit(boss, inside, kochi.pk)
    assign.assign_member_unit(boss, outside, north.pk)
    actor, staff = lead(space, f"{slug}-lead")
    assign.set_staff_unit_scope(boss, staff, south.pk)
    return space, boss, actor, (inside, outside, nowhere), (south, kochi, north)


def test_scoped_staff_see_only_their_subtree_others_see_everyone():
    space, boss, actor, (inside, outside, nowhere), _units = _setup("ob1-scope")
    assert scope.unit_paths_for(actor, space.pk) == ["/SOUTH/"]
    assert scope.unit_paths_for(boss, space.pk) is None
    assert scope.allowed_member_ids(actor, space.pk, rbac.Action.MANAGE_MEMBERS) == {inside.pk}
    assert scope.member_in_scope(actor, inside) and not scope.member_in_scope(actor, outside)
    assert not scope.member_in_scope(actor, nowhere)  # no unit: hidden from a scoped actor


def test_roster_and_per_row_actions_respect_the_scope_with_404():
    space, _boss, actor, (inside, outside, _n), _units = _setup("ob1-roster")
    client = authenticated_client(actor)
    roster = client.get(reverse("admin-memberships-roster") + f"?makerspace_id={space.pk}").json()
    ids = {row["id"] for row in roster["results"]}
    assert inside.pk in ids and outside.pk not in ids
    assert client.post(reverse("admin-membership-revoke-m2", args=[outside.pk]), {}, format="json").status_code == 404


def test_requests_narrow_through_the_unit_the_applicant_chose():
    space, _boss, actor, (inside, outside, _n), (_s, kochi, north) = _setup("ob1-requests")
    mine = MembershipRequest.objects.create(makerspace=space, user=inside.user, kind="request", state="requested",
                                            invite_email=inside.user.email)
    theirs = MembershipRequest.objects.create(makerspace=space, user=outside.user, kind="request", state="requested",
                                              invite_email=outside.user.email)
    record_request_unit(mine, kochi)
    record_request_unit(theirs, north)
    seen = authenticated_client(actor).get(reverse("admin-membership-requests") + f"?makerspace_id={space.pk}").json()
    assert {row["id"] for row in seen["results"]} == {mine.pk}


def test_scoped_actor_may_only_place_members_in_their_own_subtree():
    _space, _boss, actor, (inside, _o, _n), (_s, _k, north) = _setup("ob1-place")
    with pytest.raises(Exception) as error:
        assign.assign_member_unit(actor, inside, north.pk, action=rbac.Action.MANAGE_MEMBERS)
    assert error.value.detail["code"] == "unit_scope_forbids"


def test_space_wide_settings_are_refused_to_a_scoped_actor():
    space, _boss, actor, *_rest = _setup("ob1-wide")
    with pytest.raises(Exception) as error:
        scope.require_space_wide(actor, space.pk)
    assert error.value.detail["code"] == "unit_scope_forbids"


def test_switch_off_lifts_every_narrowing():
    space, _boss, actor, _members, _units = _setup("ob1-off-scope")
    features_off(space, "unit_scoped_staff")
    assert scope.unit_paths_for(actor, space.pk) is None
