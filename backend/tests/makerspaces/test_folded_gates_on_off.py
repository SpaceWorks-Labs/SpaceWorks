"""L17 (#97, #128 C-9): every folded route is 404 when its parent's switch is off, rows kept."""
import datetime

import pytest
from django.urls import reverse

from apps.inventory.models import InventoryAsset, InventoryProduct, TrackingMode
from apps.machines.models import Machine, MachineType
from apps.maintenance.models import MaintenanceSchedule
from apps.makerspaces.module_registry import MODULE_KEYS
from apps.makerspaces.platform import bootstrap_payload
from apps.operations.reminder_registry import registered_sources
from apps.procurement.models import ToBuyItem
from apps.warranty.models import Warranty
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import authenticated_client, make_space

pytestmark = pytest.mark.django_db
ALL = ("machines.maintenance", "machines.tobuy", "inventory.tobuy", "machines.warranty", "inventory.warranty")


@pytest.fixture
def world():
    space = make_space("folded")
    manager = staff_account(space, "folded-sm", "space_manager")
    kind = MachineType.objects.create(makerspace=space, name="Laser", slug="folded-laser")
    machine = Machine.objects.create(makerspace=space, machine_type=kind, name="Laser one")
    product = InventoryProduct.objects.create(makerspace=space, name="Meter", tracking_mode=TrackingMode.INDIVIDUAL,
                                              total_quantity=1, available_quantity=1)
    asset = InventoryAsset.objects.create(makerspace=space, product=product, asset_tag="F-1")
    schedule = MaintenanceSchedule.objects.create(machine=machine, description="Clean optics", interval_days=7,
                                                  next_due=datetime.date.today())
    printing = ToBuyItem.objects.create(makerspace=space, kind="printing", name="PLA")
    hardware = ToBuyItem.objects.create(makerspace=space, kind="hardware", name="Probe")
    Warranty.objects.create(makerspace=space, machine=machine)
    Warranty.objects.create(makerspace=space, asset=asset)
    return dict(space=space, client=authenticated_client(manager), machine=machine, asset=asset,
                schedule=schedule, printing=printing, hardware=hardware)


def switch(space, *off):
    space.refresh_from_db()
    space.enabled_features = sorted(set(space.enabled_features) | set(ALL)) if not off else sorted(
        set(space.enabled_features) - set(off))
    space.save(update_fields=["enabled_features"])


def tobuy_names(world):
    response = world["client"].get(f"/api/v1/procurement/makerspace/{world['space'].pk}/to-buy")
    return response.status_code, {row["name"] for row in response.data} if response.status_code == 200 else set()


def test_retired_module_keys_are_gone_from_the_registry():
    assert not {"maintenance", "procurement"} & MODULE_KEYS


def test_maintenance_routes_follow_machines_maintenance(world):
    space, client, machine = world["space"], world["client"], world["machine"]
    collection = reverse("admin-maintenance-schedule-list-create", args=[space.pk, machine.pk])
    detail = reverse("admin-maintenance-schedule-detail", args=[world["schedule"].pk])
    overdue = reverse("admin-maintenance-overdue", args=[space.pk])
    switch(space)
    assert {client.get(collection).status_code, client.get(overdue).status_code} == {200}
    switch(space, "machines.maintenance")
    for url in (collection, overdue):
        assert client.get(url).status_code == 404, url
    assert client.patch(detail, {"description": "y"}, format="json").status_code == 404
    assert client.post(collection, {"description": "x", "interval_days": 3}, format="json").status_code == 404
    assert MaintenanceSchedule.objects.filter(pk=world["schedule"].pk).exists()
    assert "maintenance" not in bootstrap_payload(space)["workflows"]
    switch(space)
    assert client.patch(detail, {"description": "y"}, format="json").status_code != 404


def test_one_to_buy_list_two_switches_never_hide_the_other_parent(world):
    space, client = world["space"], world["client"]
    switch(space)
    assert tobuy_names(world) == (200, {"PLA", "Probe"})
    switch(space, "machines.tobuy")
    assert tobuy_names(world) == (200, {"Probe"})
    assert client.get(reverse("procurement:to-buy-detail", args=[world["printing"].pk])).status_code == 404
    assert client.get(reverse("procurement:to-buy-detail", args=[world["hardware"].pk])).status_code == 200
    refused = client.post(f"/api/v1/procurement/makerspace/{space.pk}/to-buy?kind=printing",
                          {"name": "PETG", "quantity": 1}, format="json")
    assert refused.status_code == 404
    switch(space)
    switch(space, "inventory.tobuy")
    assert tobuy_names(world) == (200, {"PLA"})
    switch(space, "machines.tobuy", "inventory.tobuy")
    assert tobuy_names(world)[0] == 404
    assert ToBuyItem.objects.filter(makerspace=space).count() == 2


def test_warranty_follows_its_host_kind(world):
    space, client = world["space"], world["client"]
    asset_url = reverse("admin-asset-warranty", args=[world["asset"].pk])
    machine_url = reverse("admin-machine-warranty", args=[world["machine"].pk])
    report = reverse("admin-makerspace-warranties", args=[space.pk])
    switch(space)
    assert client.get(asset_url).status_code == 200 and client.get(machine_url).status_code == 200
    switch(space, "machines.warranty")
    assert client.get(machine_url).status_code == 404 and client.get(asset_url).status_code == 200
    assert {row["host_kind"] for row in client.get(report).data["results"]} == {"asset"}
    switch(space)
    switch(space, "inventory.warranty")
    assert client.get(asset_url).status_code == 404 and client.get(machine_url).status_code == 200
    switch(space, "machines.warranty", "inventory.warranty")
    assert client.get(report).status_code == 404
    assert Warranty.objects.filter(makerspace=space).count() == 2


def test_no_reminder_source_hangs_off_a_retired_module_and_off_means_no_reminders(world):
    sources = {source.key: source for source in registered_sources()}
    assert sources["maintenance.due"].module == "machines"
    assert sources["maintenance.meter"].module == "machines"
    from apps.makerspaces.platform import feature_enabled
    space = world["space"]
    switch(space)
    space.enabled_features = sorted(set(space.enabled_features) | {"maintenance.reminders"})
    space.save(update_fields=["enabled_features"])
    assert feature_enabled(space, "maintenance.reminders")
    switch(space, "machines.maintenance")
    assert not feature_enabled(space, "maintenance.reminders")


def test_low_stock_drafts_need_machines_tobuy(world):
    from apps.machines.low_stock import maybe_flag_low_stock
    from apps.machines.models import MachineConsumablePool
    space = world["space"]
    pool = MachineConsumablePool.objects.create(makerspace=space, machine=world["machine"], material="PLA", color="red",
                                                initial_grams=1000, remaining_grams=10, low_threshold_grams=50)
    switch(space, "machines.tobuy")
    assert maybe_flag_low_stock(None, pool) is None
    switch(space)
    assert maybe_flag_low_stock(None, pool) is not None
