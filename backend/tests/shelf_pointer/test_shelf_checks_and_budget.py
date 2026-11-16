"""Decision 331c: shelf checks (record, list, report row) and the embedded payload budget for a pointer with 200 poses."""
import json

import pytest
from django.urls import reverse

from apps.operations.reports_inventory_control import build_inventory_control
from tests.shelf_pointer.pointer_case import pointer_case, save_pose

pytestmark = pytest.mark.django_db(transaction=True)


def _checks(case):
    return reverse("devices:admin-shelf-checks", args=[case["space"].pk])


def test_locations_list_counts_items_and_flags_coverage_and_filters_by_prefix():
    case = pointer_case("sc-locations")
    save_pose(case, "Shelf A")
    url = reverse("devices:admin-shelf-locations", args=[case["space"].pk])
    rows = case["client"].get(url).data
    assert rows == [{"location": "Shelf A", "item_count": 1, "covered": True},
                    {"location": "Shelf B", "item_count": 2, "covered": False}]
    assert [r["location"] for r in case["client"].get(url, {"prefix": "shelf b"}).data] == ["Shelf B"]


def test_a_shelf_check_is_saved_audited_listed_and_counted_in_the_inventory_report():
    case = pointer_case("sc-record")
    body = {"scope_label": "Shelf *", "entries": [{"location": "Shelf A", "status": "ok"},
                                                   {"location": "Shelf B", "status": "attention", "note": "Bin 3 empty"}]}
    saved = case["client"].post(_checks(case), body, format="json")
    assert saved.status_code == 201, saved.data
    assert saved.data["ok_count"] == 1 and saved.data["attention_count"] == 1
    listed = case["client"].get(_checks(case))
    assert listed.data["count"] == 1 and listed.data["results"][0]["id"] == saved.data["id"]
    assert "entries" not in listed.data["results"][0]
    detail = case["client"].get(reverse("devices:admin-shelf-check-detail", args=[saved.data["id"]]))
    assert detail.data["entries"][1]["note"] == "Bin 3 empty"
    case["space"].enabled_modules = sorted(set(case["space"].enabled_modules or []) | {"stocktake"})
    case["space"].save(update_fields=["enabled_modules"])
    rows = [r for r in build_inventory_control(case["space"].pk).records if r["metric_key"] == "shelf_checks"]
    assert rows and rows[0]["count"] == 1 and rows[0]["quantity"] == 1 and rows[0]["rate_percent"] == 50.0


def test_a_shelf_check_refuses_unknown_or_repeated_locations_and_empty_walks():
    case = pointer_case("sc-refuse")
    bad = case["client"].post(_checks(case), {"entries": [{"location": "Nowhere", "status": "ok"}]}, format="json")
    assert bad.status_code == 400
    twice = case["client"].post(_checks(case), {"entries": [{"location": "Shelf A", "status": "ok"},
                                                            {"location": "Shelf A", "status": "ok"}]}, format="json")
    assert twice.status_code == 400
    assert case["client"].post(_checks(case), {"entries": []}, format="json").status_code == 400


def test_embedded_payloads_stay_small_with_200_poses_and_poses_are_not_in_hello_or_bindings():
    case = pointer_case("sc-budget")
    from apps.devices.models import AdapterBinding, AdapterPose
    binding = AdapterBinding.objects.get(pk=case["pointer_binding"])
    AdapterPose.objects.bulk_create([AdapterPose(
        makerspace=case["space"], binding=binding, target_type="storage_location", target_id=f"Shelf {i:03d}",
        pose={"kind": "pan_tilt", "pan_deg": i / 3, "tilt_deg": -i / 7, "laser_power_pct": 60}) for i in range(200)])
    sim = case["sim"]
    hello = sim.hello(["status", "events", "locate.calibrate", "locate.indicate"])
    bindings = sim.get("bindings")
    config = sim.get("config")
    clock = sim.get("time?nonce=abcd1234")
    sizes = {"hello": len(hello.content), "bindings": len(bindings.content), "config": len(config.content),
             "time": len(clock.content)}
    print("EMBEDDED_SIZES", json.dumps(sizes))
    assert "pan_deg" not in hello.content.decode() and "pan_deg" not in bindings.content.decode()
    assert sizes["hello"] < 4096 and sizes["bindings"] < 1024 and sizes["config"] < 512 and sizes["time"] < 512
    case["client"].post(reverse("devices:admin-shelf-show", args=[case["space"].pk]),
                        {"target_type": "storage_location", "target_id": "Shelf 150"}, format="json")
    lease = sim.post("commands/lease")
    print("EMBEDDED_LEASE_BYTES", len(lease.content))
    assert len(lease.content) < 1024
