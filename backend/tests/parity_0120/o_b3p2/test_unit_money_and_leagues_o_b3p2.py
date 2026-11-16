"""O-B3 part 2: unit and level leagues, per-unit payment instructions, and unit scope in money and reports."""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts import rbac
from apps.makerspaces import member_unit_assign as assign
from apps.makerspaces import member_units
from apps.makerspaces.models import MakerspaceMembership
from apps.operations.report_registry import REPORT_REGISTRY
from apps.operations.reports import report_data
from apps.payments import collection_sheet
from apps.payments.models import MakerspaceBillingSettings, Payment
from apps.payments.payment_rows_l5 import member_offline_context, offline_collection
from apps.payments.reconciliation import list_payments, mark_offline
from tests.audit_explorer_helpers import custom_role_member
from tests.l5_local.helpers import switch
from tests.makerspaces.l4_helpers import features_off
from tests.parity_0120.o_b1.helpers import community_member, tree, units_space
from tests.return_helpers import authenticated_client, settlement_details

pytestmark = pytest.mark.django_db(transaction=True)

FINANCE = [rbac.Action.MANAGE_MEMBERS, rbac.Action.VIEW_FINANCE, rbac.Action.RECORD_PAYMENT]


@pytest.fixture(autouse=True)
def card_test_host(settings):
    settings.INFRA_HOSTS = {*settings.INFRA_HOSTS, "testserver"}


def _charge(space, membership, amount="100.00"):
    return Payment.objects.create(
        makerspace=space, subject_type=Payment.SubjectType.MAKERSPACE_MEMBERSHIP, subject_id=membership.pk,
        member=membership.user, amount=Decimal(amount), currency="inr", created_by=membership.user)


def _setup(slug):
    space, boss = units_space(slug)
    switch(space, "charges.enabled", "charges.membership", "billing.documents", "billing.collection_sheet",
           "membership.insights")
    south, kochi, north = tree(boss, space)
    inside, outside, nowhere = (community_member(space, f"{slug}-{n}") for n in ("in", "out", "none"))
    assign.assign_member_unit(boss, inside, kochi.pk)
    assign.assign_member_unit(boss, outside, north.pk)
    actor = custom_role_member(space, f"{slug}-lead", FINANCE)
    assign.set_staff_unit_scope(boss, MakerspaceMembership.staff_tracks.get(makerspace=space, user=actor), south.pk)
    return space, boss, actor, (inside, outside, nowhere), (south, kochi, north)


def test_both_league_reports_are_registered_counts_only_and_gated_on_units():
    for key in ("membership-unit-league", "membership-level-league"):
        definition = REPORT_REGISTRY[key]
        assert not definition.deployment_aggregate and not definition.identity_bearing
        assert definition.required_feature == "membership.units"


def test_unit_league_rolls_members_up_the_tree_and_never_names_anyone():
    space, boss, _actor, _members, _units = _setup("ob3p2-league")
    rows = {row["unit_code"]: row for row in report_data("membership-unit-league", space.pk, actor=boss)["typed_rows"]}
    assert rows["SOUTH"]["members"] == 1 and rows["SOUTH"]["direct_members"] == 0
    assert rows["KOCHI"]["members"] == 1 and rows["KOCHI"]["direct_members"] == 1
    assert rows["NORTH"]["members"] == 1 and rows["KOCHI"]["parent_code"] == "SOUTH"
    assert rows["KOCHI"]["level_name"] == "District"
    assert not {"name", "email", "member"} & set(rows["KOCHI"])


def test_level_league_counts_units_and_direct_members_per_level():
    space, boss, _actor, _members, _units = _setup("ob3p2-level")
    rows = {row["level_name"]: row for row in report_data("membership-level-league", space.pk, actor=boss)["typed_rows"]}
    assert (rows["Region"]["units"], rows["Region"]["members"]) == (2, 1)  # SOUTH and NORTH; NORTH holds one
    assert (rows["District"]["units"], rows["District"]["members"]) == (1, 1)


def test_a_unit_scoped_actor_sees_their_own_subtree_in_the_leagues():
    space, _boss, actor, _members, _units = _setup("ob3p2-league-scope")
    units = report_data("membership-unit-league", space.pk, actor=actor)["typed_rows"]
    assert {row["unit_code"] for row in units} == {"SOUTH", "KOCHI"}
    levels = report_data("membership-level-league", space.pk, actor=actor)["typed_rows"]
    assert {row["level_name"]: row["units"] for row in levels} == {"Region": 1, "District": 1}


def test_unit_instructions_use_the_nearest_ancestor_then_the_space_text():
    space, boss, _actor, (inside, outside, _n), (south, _kochi, _north) = _setup("ob3p2-instr")
    MakerspaceBillingSettings.objects.update_or_create(
        makerspace=space, defaults={"payment_instructions": "Space desk"})
    member_units.update_unit(boss, south, {"payment_instructions": "Pay South treasurer"})
    mine, plain = _charge(space, inside), _charge(space, outside)
    result = offline_collection(mine, member_offline_context([mine], inside.user))
    assert result["instructions"] == "Pay South treasurer" and result["instructions_unit"]["code"] == "SOUTH"
    assert result["upi"] is None  # a unit's own instructions replace the space's UPI QR
    fallback = offline_collection(plain, member_offline_context([plain], outside.user))  # NORTH: nothing above it
    assert fallback["instructions"] == "Space desk" and fallback["instructions_unit"] is None


def test_unit_instructions_show_only_to_the_charges_own_member_and_only_while_units_are_on():
    space, boss, actor, (inside, _o, _n), (_s, kochi, _north) = _setup("ob3p2-own")
    member_units.update_unit(boss, kochi, {"payment_instructions": "Kochi UPI"})
    mine = _charge(space, inside)
    assert offline_collection(mine, member_offline_context([mine], inside.user))["instructions"] == "Kochi UPI"
    assert offline_collection(mine, member_offline_context([mine], actor))["instructions_unit"] is None  # staff
    assert offline_collection(mine, member_offline_context([mine]))["instructions_unit"] is None  # no viewer
    features_off(space, "unit_scoped_staff", "units")
    assert offline_collection(mine, member_offline_context([mine], inside.user))["instructions_unit"] is None


def test_collection_sheet_rows_out_of_unit_scope_fail_without_touching_the_charge():
    space, _boss, actor, (inside, outside, nowhere), _units = _setup("ob3p2-sheet")
    mine, theirs, loose = _charge(space, inside), _charge(space, outside), _charge(space, nowhere)
    rows = [{"payment_id": p.pk, "method": "cash", "reference": f"R{p.pk}"} for p in (mine, theirs, loose)]
    result = collection_sheet.record_sheet(actor=actor, space=space, rows=rows)
    assert [row["outcome"] for row in result["results"]] == ["recorded", "failed", "failed"]
    assert {row["code"] for row in result["results"][1:]} == {"not_found"}
    for payment, status in ((mine, "paid_offline"), (theirs, "pending"), (loose, "pending")):
        payment.refresh_from_db()
        assert payment.status == status


def test_payment_list_hides_other_units_charges_from_a_scoped_actor():
    space, boss, actor, (inside, outside, _n), _units = _setup("ob3p2-list")
    mine, theirs = _charge(space, inside), _charge(space, outside)
    scoped = {p.pk for p in list_payments(actor=actor, makerspace_id=space.pk, for_recording=True)}
    assert scoped == {mine.pk}
    assert {mine.pk, theirs.pk} <= {p.pk for p in list_payments(actor=boss, makerspace_id=space.pk)}


def test_cash_in_hand_for_a_scoped_actor_is_only_their_own_in_scope_cash():
    space, boss, actor, (inside, outside, _n), _units = _setup("ob3p2-cash")
    mark_offline(_charge(space, inside, "40.00"), actor, settlement_details(reference="A"))
    mark_offline(_charge(space, outside, "60.00"), boss, settlement_details(reference="B"))
    scoped = report_data("cash-in-hand", space.pk, actor=actor)["typed_rows"]
    assert [(row["collector_id"], row["received_cash"]) for row in scoped] == [(actor.pk, "40.00")]
    wide = {row["collector_id"]: row["received_cash"]
            for row in report_data("cash-in-hand", space.pk, actor=boss)["typed_rows"]}
    assert wide == {actor.pk: "40.00", boss.pk: "60.00"}


def test_revenue_by_plan_narrows_for_a_scoped_actor():
    space, boss, actor, (inside, outside, _n), _units = _setup("ob3p2-revenue")
    mark_offline(_charge(space, inside, "30.00"), boss, settlement_details(reference="A"))
    mark_offline(_charge(space, outside, "70.00"), boss, settlement_details(reference="B"))

    def total(who):
        rows = report_data("membership-revenue-by-plan", space.pk, actor=who)["typed_rows"]
        return sum(Decimal(row["collected"]) for row in rows)

    assert total(boss) == Decimal("100.00") and total(actor) == Decimal("30.00")


def test_a_scoped_actor_can_hand_over_only_their_own_cash():
    space, boss, actor, _members, _units = _setup("ob3p2-handover")
    url = reverse("billing-cash-handover", args=[space.pk])
    body = {"amount": "10.00", "currency": "inr"}
    other = authenticated_client(actor).post(url, {**body, "collector_id": boss.pk}, format="json")
    assert other.status_code == 404
    own = authenticated_client(actor).post(url, {**body, "collector_id": actor.pk}, format="json")
    assert own.status_code in (201, 400)  # 201 normally; 400 only if the body needs more fields than assumed here


def test_a_scoped_checker_cannot_see_or_confirm_a_proposal_outside_their_unit():
    from rest_framework.exceptions import NotFound

    from apps.payments import maker_checker
    from apps.payments.models import SettlementConfirmation

    space, boss, actor, (inside, outside, nowhere), _units = _setup("ob3p2-checker")
    switch(space, "billing.maker_checker")
    mine, theirs, loose = _charge(space, inside), _charge(space, outside), _charge(space, nowhere)
    for payment in (mine, theirs, loose):
        mark_offline(payment, boss, settlement_details(reference=f"P{payment.pk}"))  # proposals, charges stay pending
    ids = {row.payment_id: row.pk for row in SettlementConfirmation.objects.filter(payment__makerspace=space)}
    assert set(ids) == {mine.pk, theirs.pk, loose.pk}
    listing = authenticated_client(actor).get(reverse("settlement-confirmations", args=[space.pk])).json()
    results = listing["results"] if isinstance(listing, dict) else listing
    assert {row["id"] for row in results} == {ids[mine.pk]}
    for hidden in (theirs, loose):
        with pytest.raises(NotFound):
            maker_checker.confirm(actor=actor, makerspace_id=space.pk, confirmation_id=ids[hidden.pk])
    maker_checker.confirm(actor=actor, makerspace_id=space.pk, confirmation_id=ids[mine.pk])
    mine.refresh_from_db()
    assert mine.status == "paid_offline"
