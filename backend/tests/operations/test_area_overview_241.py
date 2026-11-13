"""Decision 241: grouped area views. Each area manager reads only their area's rows; the Space
Manager reads every area, grouped by area (machines: type, then machine; inventory: category)."""

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.inventory.models import Category
from apps.machines.models import MachineConsumablePool
from apps.maintenance.repairs import services_issues as svc
from apps.payments import ledger_api
from apps.procurement.models import ToBuyItem
from tests.fixed_roles.helpers import staff_account
from tests.handout_roles import make_handout_member
from tests.l5_local.helpers import accountless, dues, setup
from tests.l5_local.helpers import switch as feature
from tests.maintenance.l16_helpers import in_house, switch, world
from tests.payments.account_helpers import make_payer
from tests.return_helpers import authenticated_client, make_member, make_product

pytestmark = pytest.mark.django_db
D = Decimal


def _get(user, space, section, **params):
    return authenticated_client(user).get(reverse("admin-area-overview", args=[space.pk, section]), params)


def _keys(body):
    return [group["key"] for group in body["groups"]]


def _child(group, key):
    return next(child for child in group["children"] if child["key"] == key)


def _area(body, area):
    return next(group for group in body["groups"] if group["key"] == f"area:{area}")


def _expense(space, actor, domain, source, amount, machine_type=None):
    return ledger_api.record_expense(space, domain, machine_type, amount, "inr", "cash", f"R-{source}", None,
                                     "manual", source, actor, category="repair")


@pytest.fixture
def w():
    w = world("ov241", features=(
        "machines.repairs", "machines.maintenance", "machines.issue_reporting", "inventory.repairs",
        "inventory.maintenance", "inventory.issue_reporting", "bookings.room_repairs", "bookings.room_maintenance",
        "bookings.issue_reporting", "inventory.tobuy", "machines.tobuy", "inventory.consumables",
        "inventory.warranty", "machines.warranty", "finance.ledger", "charges.enabled", "charges.membership",
        "billing.documents"))
    w.space.enabled_modules = sorted(set(w.space.enabled_modules or []) | {"staff_admin", "events", "shop"})
    w.space.save(update_fields=["enabled_modules"])
    w.mm_laser = staff_account(w.space, "ov241-mm", "machine_manager", machine_types=[w.kind])
    w.bm = make_member("ov241-bm", w.space, membership_role="booking_manager")
    w.em = make_member("ov241-em", w.space, membership_role="event_manager")
    w.shop = make_member("ov241-shop", w.space, membership_role="shop_manager")
    w.handover = make_handout_member("ov241-handover", w.space)
    return w


# Finance ---------------------------------------------------------------------------------------

def _money(w):
    _expense(w.space, w.manager, "inventory", "inv", "40.00")
    _expense(w.space, w.manager, "machines", "las", "15.00", machine_type=w.kind)
    _expense(w.space, w.manager, "machines", "cnc", "25.00", machine_type=w.other_kind)
    _expense(w.space, w.manager, "bookings", "room", "10.00")
    _expense(w.space, w.manager, "shop", "shelf", "5.00")
    accountless(w.space, w.manager, amount="75.00")  # a pending loan deposit: owed to lending
    dues(w.space, make_payer("ov241-payer", w.space), "30.00")


def test_finance_space_manager_sees_every_area_grouped_with_totals(w):
    _money(w)
    body = _get(w.manager, w.space, "finance").json()
    assert {"area:inventory", "area:machines", "area:bookings", "area:shop", "area:membership"} <= set(_keys(body))
    machines = _area(body, "machines")
    assert [child["key"] for child in machines["children"]] == [f"machine_type:{w.other_kind.pk}",
                                                                 f"machine_type:{w.kind.pk}"]
    laser = _child(machines, f"machine_type:{w.kind.pk}")
    assert laser["label"] == "Laser" and laser["finance"][0]["expenses"] == "15.00"
    assert laser["children"][0]["key"] == "machine:none"  # a ledger expense names its type, not one machine
    assert machines["finance"][0]["expenses"] == "40.00"
    lending = _child(_area(body, "inventory"), "domain:loans")
    assert lending["finance"][0]["owed"] == "75.00" and lending["attention"] == 1
    assert body["totals"]["finance"][0]["owed"] == "105.00"
    assert set(body["areas"]) >= {"inventory", "machines", "bookings", "events", "shop", "membership"}


@pytest.mark.parametrize("who,areas", [
    ("im", {"area:inventory"}), ("bm", {"area:bookings"}), ("shop", {"area:shop"}), ("mm_laser", {"area:machines"}),
])
def test_finance_each_area_manager_gets_only_their_area(w, who, areas):
    _money(w)
    body = _get(getattr(w, who), w.space, "finance").json()
    assert set(_keys(body)) == areas
    assert "membership" not in body["areas"] and "donations" not in body["areas"]


def test_finance_machine_manager_sees_only_their_machine_types(w):
    _money(w)
    machines = _area(_get(w.mm_laser, w.space, "finance").json(), "machines")
    assert [child["key"] for child in machines["children"]] == [f"machine_type:{w.kind.pk}"]
    assert machines["finance"][0]["expenses"] == "15.00"


def test_finance_event_manager_sees_events_only_and_is_refused_without_an_area(w):
    _money(w)
    assert _keys(_get(w.em, w.space, "finance").json()) == []
    assert _get(w.tech, w.space, "finance").status_code == 404
    assert _get(w.handover, w.space, "finance").status_code == 404


def test_finance_off_switch_and_area_filter(w):
    _money(w)
    body = _get(w.manager, w.space, "finance", area="machines").json()
    assert _keys(body) == ["area:machines"]
    assert _get(w.manager, w.space, "finance", area="nowhere").status_code == 400
    feature(w.space, "finance.ledger", on=False)
    assert _get(w.manager, w.space, "finance").status_code == 404


def test_finance_payout_columns_need_an_interactive_session(w, monkeypatch):
    _money(w)
    assert "payouts" in _get(w.manager, w.space, "finance").json()["totals"]["finance"][0]
    monkeypatch.setattr("apps.payments.payout_session.full_session", lambda request: False)
    row = _get(w.manager, w.space, "finance").json()["totals"]["finance"][0]
    assert "payouts" not in row and "net" not in row and "money_out" not in row and row["owed"] == "105.00"


# To-Buy ----------------------------------------------------------------------------------------

def _shopping(w):
    tools = Category.objects.create(makerspace=w.space, name="Hand tools", slug="hand-tools")
    drill = make_product(w.space, name="Drill bits", category=tools)
    ToBuyItem.objects.create(makerspace=w.space, kind="hardware", name="More bits", quantity=2,
                             estimated_unit_cost=D("3.00"), source_product=drill)
    ToBuyItem.objects.create(makerspace=w.space, kind="printing", name="Laser lens", machine_type=w.kind,
                             resulting_machine=w.machine, estimated_unit_cost=D("20.00"))
    ToBuyItem.objects.create(makerspace=w.space, kind="printing", name="CNC bit", machine_type=w.other_kind,
                             estimated_unit_cost=D("8.00"))
    ToBuyItem.objects.create(makerspace=w.space, kind="hardware", name="Bought already", status="received")
    return tools


def test_tobuy_space_manager_groups_by_area_type_machine_and_category(w):
    tools = _shopping(w)
    body = _get(w.manager, w.space, "tobuy").json()
    assert _keys(body) == ["area:inventory", "area:machines"]
    inventory = _area(body, "inventory")
    assert [child["key"] for child in inventory["children"]] == [f"category:{tools.pk}"]
    assert inventory["money"] == [{"currency": "", "amount": "6.00"}]
    laser = _child(_area(body, "machines"), f"machine_type:{w.kind.pk}")
    assert _child(laser, f"machine:{w.machine.pk}")["items"][0]["label"] == "Laser lens"
    assert body["totals"]["count"] == 3  # the received row is not "to buy" by default
    assert _get(w.manager, w.space, "tobuy", status="all").json()["totals"]["count"] == 4


def test_tobuy_area_managers_get_their_own_stream_and_types(w):
    _shopping(w)
    assert _keys(_get(w.im, w.space, "tobuy").json()) == ["area:inventory"]
    machines = _get(w.mm_laser, w.space, "tobuy").json()
    assert _keys(machines) == ["area:machines"]
    assert [child["key"] for child in _area(machines, "machines")["children"]] == [f"machine_type:{w.kind.pk}"]
    assert _get(w.bm, w.space, "tobuy").status_code == 404
    assert _get(w.tech, w.space, "tobuy").status_code == 404


# Consumables -----------------------------------------------------------------------------------

def test_consumables_group_by_category_and_by_type_then_machine(w):
    tools = Category.objects.create(makerspace=w.space, name="Shop stock", slug="shop-stock")
    make_product(w.space, name="Sandpaper", category=tools, is_consumable=True, total_quantity=2,
                 available_quantity=1, reorder_point=2)
    MachineConsumablePool.objects.create(makerspace=w.space, machine=w.machine, material="Acrylic",
                                         initial_grams=D("100"), remaining_grams=D("50"))
    MachineConsumablePool.objects.create(makerspace=w.space, machine=w.other, material="Plywood",
                                         initial_grams=D("100"), remaining_grams=D("90"))
    body = _get(w.manager, w.space, "consumables").json()
    inventory = _area(body, "inventory")
    assert inventory["children"][0]["key"] == f"category:{tools.pk}" and inventory["attention"] == 1
    laser = _child(_area(body, "machines"), f"machine_type:{w.kind.pk}")
    assert laser["children"][0]["key"] == f"machine:{w.machine.pk}"
    scoped = _get(w.mm_laser, w.space, "consumables").json()
    assert _keys(scoped) == ["area:machines"]
    assert [child["key"] for child in _area(scoped, "machines")["children"]] == [f"machine_type:{w.kind.pk}"]
    assert _keys(_get(w.im, w.space, "consumables").json()) == ["area:inventory"]


# Repairs ---------------------------------------------------------------------------------------

def test_repairs_group_per_area_and_the_technician_sees_only_assigned_jobs(w):
    laser_job = svc.open_issue(w.manager, w.space, subject_type="machine", subject=w.machine, title="Lens cracked")
    svc.open_issue(w.manager, w.space, subject_type="machine", subject=w.other, title="Spindle noise")
    svc.open_issue(w.manager, w.space, subject_type="bookable_space", subject=w.room, title="Leak")
    svc.open_issue(w.manager, w.space, subject_type="inventory_product", subject=w.product, title="Tip loose")
    body = _get(w.manager, w.space, "repairs").json()
    assert _keys(body) == ["area:bookings", "area:inventory", "area:machines"]
    assert _child(_area(body, "bookings"), f"room:{w.room.pk}")["count"] == 1
    assert [child["key"] for child in _area(_get(w.mm_laser, w.space, "repairs").json(), "machines")["children"]] \
        == [f"machine_type:{w.kind.pk}"]
    assert _keys(_get(w.bm, w.space, "repairs").json()) == ["area:bookings"]
    assert _keys(_get(w.im, w.space, "repairs").json()) == ["area:inventory"]
    assert _keys(_get(w.tech, w.space, "repairs").json()) == []
    # open_issue starts a staff-opened repair already triaged (services_issues.open_issue), so assign directly.
    svc.assign(w.manager, laser_job, contact=in_house(w))
    tech = _get(w.tech, w.space, "repairs").json()
    laser = _child(_area(tech, "machines"), f"machine_type:{w.kind.pk}")
    assert [item["label"] for item in _child(laser, f"machine:{w.machine.pk}")["items"]] == ["Lens cracked"]
    assert "reporter" not in str(tech)


# Warranties and refusals ---------------------------------------------------------------------

def test_warranties_group_machines_by_type_and_assets_by_category(w):
    body = _get(w.manager, w.space, "warranties").json()
    assert "area:machines" in _keys(body)
    scoped = _get(w.mm_laser, w.space, "warranties").json()
    assert [child["key"] for child in _area(scoped, "machines")["children"]] == [f"machine_type:{w.kind.pk}"]
    assert _get(w.bm, w.space, "warranties").status_code == 403


def test_unknown_section_handover_and_foreign_space_are_refused(w):
    _other, foreign_manager, _payer = setup("ov241-other", "finance.ledger")
    assert _get(w.manager, w.space, "nothing").status_code == 404
    assert _get(w.handover, w.space, "tobuy").status_code == 404
    assert _get(w.handover, w.space, "consumables").status_code == 404
    assert _get(foreign_manager, w.space, "tobuy").status_code == 404
    assert _get(foreign_manager, w.space, "finance").status_code == 404
    switch(w.space, off=("inventory.tobuy", "machines.tobuy"))
    assert _get(w.manager, w.space, "tobuy").status_code == 404
