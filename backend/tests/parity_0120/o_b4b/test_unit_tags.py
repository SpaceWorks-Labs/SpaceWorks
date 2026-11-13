"""O-B4 part 2: unit tags and numbering tokens on member cards, unit-scoped card verify, and the unit GET."""
import pytest
from django.urls import reverse

from apps.card_designs import data_fields, numbering
from apps.card_designs.holders_member import unit_values
from apps.makerspaces import member_card_services as services
from apps.makerspaces import member_unit_assign as assign
from tests.parity_0120.o_b1.helpers import community_member, lead, tree, units_space
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db(transaction=True)


def test_unit_tags_are_valid_design_fields():
    for tag in ("unit", "unit_code", "units", "level1", "level2", "level3", "level4"):
        assert data_fields.valid_tag(tag) and tag in data_fields.SAMPLE_SHORT


def test_unit_values_and_codes_read_the_live_chain():
    space, boss = units_space("ob4b-tags")
    _south, kochi, _north = tree(boss, space)
    member = community_member(space, "ob4b-tag-m")
    assert unit_values(member)["unit"] == "" and numbering.unit_codes(member) == ()
    assign.assign_member_unit(boss, member, kochi.pk)
    values = unit_values(member)
    assert values["unit"] == "Kochi" and values["unit_code"] == kochi.code
    assert values["units"] == "South / Kochi" and values["level1"] == "South" and values["level2"] == "Kochi"
    assert values["level3"] == "" and numbering.unit_codes(member) == ("SOUTH", kochi.code)


def test_unit_tokens_render_in_a_number():
    assert numbering.render("{U1}-{UNIT}-{SEQ:3}", seq=7, units=("SOUTH", "KOC")) == "SOUTH-KOC-007"
    assert numbering.render("{U3}-{SEQ}", seq=1, units=("A",)) == "NA-1"


def test_member_card_snapshot_carries_unit_tags():
    space, boss = units_space("ob4b-snap")
    _south, kochi, _north = tree(boss, space)
    member = community_member(space, "ob4b-snap-m")
    assign.assign_member_unit(boss, member, kochi.pk)
    card = services.issue_card(boss, member)
    from apps.card_designs.holders import registered
    assert registered()["member_card"].snapshot(card)["unit"] == "Kochi"


def test_verify_staff_panel_respects_unit_scope():
    from apps.card_designs.views_verify_staff import in_member_scope
    space, boss = units_space("ob4b-verify")
    south, kochi, north = tree(boss, space)
    inside, outside = community_member(space, "ob4b-in"), community_member(space, "ob4b-out")
    assign.assign_member_unit(boss, inside, kochi.pk)
    assign.assign_member_unit(boss, outside, north.pk)
    actor, staff = lead(space, "ob4b-lead")
    assign.set_staff_unit_scope(boss, staff, south.pk)
    assert in_member_scope(actor, inside) and not in_member_scope(actor, outside)
    assert in_member_scope(boss, outside)


def test_membership_unit_get_mirrors_put_scoping():
    space, boss = units_space("ob4b-get")
    south, kochi, north = tree(boss, space)
    inside, outside = community_member(space, "ob4b-get-in"), community_member(space, "ob4b-get-out")
    assign.assign_member_unit(boss, inside, kochi.pk)
    assign.assign_member_unit(boss, outside, north.pk)
    actor, staff = lead(space, "ob4b-get-lead")
    assign.set_staff_unit_scope(boss, staff, south.pk)

    def url(m):
        return reverse("admin-membership-unit", args=[space.pk, m.pk])

    client = authenticated_client(actor)
    body = client.get(url(inside)).json()
    assert body["membership_id"] == inside.pk and body["unit"]["id"] == kochi.pk
    assert client.get(url(outside)).status_code == 404  # outside the lead's subtree
    assert authenticated_client(boss).get(url(outside)).json()["unit"]["id"] == north.pk
    _other, other_boss = units_space("ob4b-get-other")
    assert authenticated_client(other_boss).get(url(inside)).status_code == 404  # cross-tenant
