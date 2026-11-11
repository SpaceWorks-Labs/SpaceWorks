"""O-B2: one member filter contract (register = roster = card-job resolver), unit scope, and bulk register actions."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts import rbac
from apps.admin_api.member_register_filters import apply_member_filters, clean_params, register_params
from apps.makerspaces import member_register_bulk as bulk
from apps.makerspaces import member_unit_assign as assign
from apps.makerspaces.membership_plan_services import create_term
from apps.makerspaces.models import MakerspaceMembership, MembershipTitle
from tests.makerspaces.l4_helpers import features_on, plan
from tests.parity_0120.o_b1.helpers import community_member, lead, tree, units_space
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db(transaction=True)


def _space(slug):
    space, boss = units_space(slug)
    features_on(space, "register_bulk", "titles", "register_tools", "renewal_desk", "records")
    return space, boss


def _members(space):
    return MakerspaceMembership.objects.filter(makerspace=space, user__account_kind="member")


def test_unknown_filter_keys_are_refused_and_empty_values_dropped():
    assert clean_params({"q": "x", "unit": "", "chip": None}) == {"q": "x"}
    with pytest.raises(ValidationError):
        clean_params({"nope": "1"})
    with pytest.raises(ValidationError):
        register_params({"standing": "bogus"})
    assert register_params({"standing": "ending_soon"}) == {"chip": "expiring"}


def test_search_matches_names_and_member_numbers_and_chips_use_the_register_standings():
    space, boss = _space("ob2-filter-chips")
    south, kochi, north = tree(boss, space)
    ending = community_member(space, "ob2-ending")
    fresh = community_member(space, "ob2-fresh")
    create_term(boss, ending, plan(space), starts_at=timezone.now() - timedelta(days=25))
    ending.refresh_from_db()
    found = apply_member_filters(_members(space), {"q": "ob2-ending"}, space)
    assert list(found) == [ending]
    by_number = apply_member_filters(_members(space), {"q": f"#{ending.member_number}"}, space)
    assert ending in by_number
    assert list(apply_member_filters(_members(space), {"chip": "expiring"}, space)) == [ending]
    assert list(apply_member_filters(_members(space), {"chip": "no_term"}, space)) == [fresh]
    with pytest.raises(ValidationError):
        apply_member_filters(_members(space), {"chip": "bogus"}, space)


def test_unit_title_and_request_chips():
    space, boss = _space("ob2-filter-unit")
    south, kochi, north = tree(boss, space)
    a, b = community_member(space, "ob2-a"), community_member(space, "ob2-b")
    assign.assign_member_unit(boss, a, kochi.pk)
    assign.assign_member_unit(boss, b, north.pk)
    assert list(apply_member_filters(_members(space), {"unit": str(south.pk)}, space)) == [a]  # subtree
    assert list(apply_member_filters(_members(space), {"unit": "999999"}, space)) == []
    title = MembershipTitle.objects.create(makerspace=space, name="Treasurer", colour="")
    from apps.makerspaces.membership_titles import assign as give_title
    give_title(boss, b, title)
    assert list(apply_member_filters(_members(space), {"title": str(title.pk)}, space)) == [b]


def test_a_scoped_lead_is_narrowed_inside_the_filter_itself():
    space, boss = _space("ob2-filter-scope")
    south, kochi, north = tree(boss, space)
    inside, outside = community_member(space, "ob2-in"), community_member(space, "ob2-out")
    assign.assign_member_unit(boss, inside, kochi.pk)
    assign.assign_member_unit(boss, outside, north.pk)
    actor, staff_row = lead(space, "ob2-filter-lead")
    assign.set_staff_unit_scope(boss, staff_row, south.pk)
    everyone = apply_member_filters(_members(space), {}, space, actor=actor)
    assert list(everyone) == [inside]
    widened = apply_member_filters(_members(space), {"unit": str(north.pk)}, space, actor=actor)
    assert list(widened) == []  # a filter can never widen the scope


def test_register_roster_and_card_resolver_select_the_same_members():
    from apps.card_designs.job_targets_filter import resolve
    from apps.makerspaces.member_card_services import issue_card
    space, boss = _space("ob2-parity")
    south, kochi, north = tree(boss, space)
    inside, outside = community_member(space, "ob2-par-in"), community_member(space, "ob2-par-out")
    assign.assign_member_unit(boss, inside, kochi.pk)
    assign.assign_member_unit(boss, outside, north.pk)
    card = issue_card(boss, inside)
    issue_card(boss, outside)
    params = {"unit": str(south.pk)}
    client = authenticated_client(boss)
    roster = client.get(reverse("admin-memberships-roster"), {"makerspace_id": space.pk, **params}).json()["results"]
    register = client.get(reverse("admin-member-register", args=[space.pk]), params).json()
    assert [row["id"] for row in roster] == [inside.pk]
    assert [row["membership_id"] for row in register] == [inside.pk] and register[0]["unit"] == "KOCHI"
    assert resolve(boss, space, params) == [card.pk]


def test_bulk_assign_title_gives_a_result_per_member_and_refuses_out_of_scope_rows():
    space, boss = _space("ob2-bulk-title")
    south, kochi, north = tree(boss, space)
    inside, outside = community_member(space, "ob2-bulk-in"), community_member(space, "ob2-bulk-out")
    assign.assign_member_unit(boss, inside, kochi.pk)
    assign.assign_member_unit(boss, outside, north.pk)
    actor, staff_row = lead(space, "ob2-bulk-lead")
    assign.set_staff_unit_scope(boss, staff_row, south.pk)
    title = MembershipTitle.objects.create(makerspace=space, name="Lead", colour="")
    results = bulk.apply_bulk(actor, space, "assign_title", membership_ids=[inside.pk, outside.pk, 999999],
                              options={"title_id": title.pk})
    assert results == [{"id": inside.pk, "ok": True, "code": ""}, {"id": outside.pk, "ok": False, "code": "not_found"},
                       {"id": 999999, "ok": False, "code": "not_found"}]
    assert inside.title_assignments.filter(title=title).exists() and not outside.title_assignments.exists()


def test_one_failing_row_never_blocks_the_others_and_move_unit_works():
    space, boss = _space("ob2-bulk-partial")
    south, kochi, north = tree(boss, space)
    a, b = community_member(space, "ob2-part-a"), community_member(space, "ob2-part-b")
    results = bulk.apply_bulk(boss, space, "move_unit", membership_ids=[a.pk, b.pk], options={"unit_id": kochi.pk})
    assert [item["ok"] for item in results] == [True, True]
    results = bulk.apply_bulk(boss, space, "issue_cards", membership_ids=[a.pk, a.pk, b.pk])
    assert [item["ok"] for item in results] == [True, True]  # duplicate id collapsed
    again = bulk.apply_bulk(boss, space, "issue_cards", membership_ids=[a.pk, b.pk])
    assert [item["ok"] for item in again] == [False, False]  # already hold a card -> per-row refusal, no exception
    email = bulk.apply_bulk(boss, space, "email_cards", membership_ids=[a.pk])
    assert email[0]["code"] in {"not_sent", ""}  # sent or refused by the card-email rules, never an exception


def test_bulk_needs_its_switch_the_rbac_action_a_valid_selection_and_at_most_200_rows():
    space, boss = _space("ob2-bulk-rules")
    member = community_member(space, "ob2-rules-member")
    with pytest.raises(ValidationError):
        bulk.apply_bulk(boss, space, "assign_title", membership_ids=[member.pk], options={})
    with pytest.raises(ValidationError):
        bulk.apply_bulk(boss, space, "move_unit", membership_ids=[member.pk], filter_params={}, options={})
    ids = list(range(1, 400))
    assert len(bulk.select_ids(boss, space, bulk.MANAGE, ids, None)) == bulk.MAX_ROWS
    from tests.audit_explorer_helpers import custom_role_member
    nobody = custom_role_member(space, "ob2-no-cards", [rbac.Action.MANAGE_MEMBERS])
    with pytest.raises(PermissionDenied):
        bulk.apply_bulk(nobody, space, "issue_cards", membership_ids=[member.pk])
    from apps.makerspaces.guards import SurfaceOff
    from tests.makerspaces.l4_helpers import features_off
    features_off(space, "register_bulk")
    with pytest.raises(SurfaceOff):
        bulk.apply_bulk(boss, space, "move_unit", membership_ids=[member.pk], options={"unit_id": None})


def test_bulk_route_shape_and_audit_summary():
    space, boss = _space("ob2-bulk-route")
    south, kochi, north = tree(boss, space)
    a = community_member(space, "ob2-route-a")
    client = authenticated_client(boss)
    response = client.post(reverse("admin-member-register-bulk", args=[space.pk]),
                           {"action": "move_unit", "membership_ids": [a.pk], "unit_id": kochi.pk}, format="json")
    assert response.status_code == 200 and response.json() == [{"id": a.pk, "ok": True, "code": ""}]
    from apps.audit.models import AuditLog
    summary = AuditLog.objects.filter(makerspace=space, action="membership.register_bulk_applied").get()
    assert summary.meta == {"bulk_action": "move_unit", "rows": 1, "applied": 1, "refused": 0}
    assert client.post(reverse("admin-member-register-bulk", args=[space.pk]),
                       {"action": "move_unit", "unit_id": 1}, format="json").status_code == 400
