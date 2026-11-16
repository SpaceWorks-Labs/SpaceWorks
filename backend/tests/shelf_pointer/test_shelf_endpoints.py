"""Decision 331a/b: coverage, "show on shelf" and clear are staff-only, never return a pose, 404 with the switch off."""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from tests.parity_0120.adapter_api.adapter_case import plain_member
from tests.shelf_pointer.pointer_case import pointer_case, save_pose, set_caps

pytestmark = pytest.mark.django_db(transaction=True)


def _url(name, case):
    return reverse(f"devices:admin-shelf-{name}", args=[case["space"].pk])


def _targets(case, *keys):
    return {"targets": [{"target_type": t, "target_id": str(i)} for t, i in keys]}


def test_coverage_says_covered_or_not_and_never_a_pose():
    case = pointer_case("se-coverage")
    products = case["products"]
    save_pose(case, "Shelf A")
    save_pose(case, str(products["Bolts"].pk), {"pan": 1, "tilt": 2}, target_type="item")
    body = _targets(case, ("storage_location", "Shelf A"), ("storage_location", "Shelf B"),
                    ("item", products["Resistors"].pk), ("item", products["Bolts"].pk), ("item", products["Nuts"].pk))
    response = case["client"].post(_url("coverage", case), body, format="json")
    assert response.status_code == 200, response.data
    covered = [row["covered"] for row in response.data["results"]]
    assert covered == [True, False, True, True, False]  # Resistors via Shelf A, Bolts own pose, Nuts uncovered
    assert "pan" not in str(response.data) and "laser" not in str(response.data)


def test_show_queues_a_clamped_command_audits_and_never_echoes_the_pose():
    case = pointer_case("se-show")
    save_pose(case, "Shelf A")
    set_caps(case, laser_max_power_pct=20, max_on_seconds=4)
    shown = case["client"].post(_url("show", case), {"target_type": "item", "target_id": str(case["products"]["Resistors"].pk),
                                                     "duration_seconds": 300}, format="json")
    assert shown.status_code == 201 and shown.data == {"sent": 1}
    command = case["pointer"].poll_once()
    assert command["params"]["duration_seconds"] == 4 and command["params"]["pose"]["laser_power_pct"] == 20
    assert case["pointer"].log[-1].startswith("points kind pan_tilt") and "pan_deg 12.5" in case["pointer"].log[-1] and "for 4 s" in case["pointer"].log[-1]
    row = AuditLog.objects.filter(action="devices.adapter_shelf_shown", makerspace=case["space"]).get()
    assert "pan_deg" not in str(row.meta) and row.meta["clamped"] is True
    uncovered = case["client"].post(_url("show", case), {"target_type": "storage_location", "target_id": "Shelf B"},
                                    format="json")
    assert uncovered.status_code == 404


def test_clear_switches_off_every_pointer_and_is_audited():
    case = pointer_case("se-clear")
    save_pose(case, "Shelf A")
    case["client"].post(_url("show", case), {"target_type": "storage_location", "target_id": "Shelf A"}, format="json")
    case["pointer"].poll_once()
    assert case["pointer"].lit
    cleared = case["client"].post(_url("clear", case), {}, format="json")
    assert cleared.status_code == 201 and cleared.data == {"sent": 1}
    case["pointer"].poll_once()
    assert not case["pointer"].lit
    assert AuditLog.objects.filter(action="devices.adapter_shelf_cleared", makerspace=case["space"]).count() == 1


def test_members_get_403_and_a_space_with_the_switch_off_gets_404_everywhere():
    case = pointer_case("se-gates")
    save_pose(case, "Shelf A")
    member = APIClient()
    member.force_authenticate(plain_member("se-gates-m", case["space"]))
    for name, body in (("coverage", _targets(case, ("storage_location", "Shelf A"))),
                       ("show", {"target_type": "storage_location", "target_id": "Shelf A"}), ("clear", {})):
        assert member.post(_url(name, case), body, format="json").status_code in (403, 404)
    assert member.get(_url("locations", case)).status_code in (403, 404)
    case["space"].enabled_features = [f for f in case["space"].enabled_features if f != "machines.integrations"]
    case["space"].save(update_fields=["enabled_features"])
    for name, body in (("coverage", _targets(case, ("storage_location", "Shelf A"))),
                       ("show", {"target_type": "storage_location", "target_id": "Shelf A"}), ("clear", {})):
        assert case["client"].post(_url(name, case), body, format="json").status_code == 404
    assert case["client"].get(_url("locations", case)).status_code == 404
    assert case["client"].get(_url("checks", case)).status_code == 404


def test_coverage_refuses_more_than_two_hundred_targets():
    case = pointer_case("se-many")
    body = _targets(case, *[("item", i) for i in range(201)])
    assert case["client"].post(_url("coverage", case), body, format="json").status_code == 400


def test_a_disabled_pointer_covers_nothing():
    case = pointer_case("se-disabled")
    save_pose(case, "Shelf A")
    case["client"].delete(reverse("devices:admin-adapter-binding-detail", args=[case["pointer_binding"]]))
    body = _targets(case, ("storage_location", "Shelf A"))
    assert case["client"].post(_url("coverage", case), body, format="json").data["results"][0]["covered"] is False
