"""Decision 331 addendum: pose kinds are validated, the laser caps are enforced by the server, clear is never capped."""
import pytest
from django.urls import reverse

from tests.shelf_pointer.pointer_case import PAN_TILT, pointer_case, save_pose, set_caps

pytestmark = pytest.mark.django_db(transaction=True)


def _indicate(case, **body):
    return case["client"].post(reverse("devices:admin-adapter-indicate", args=[case["pointer_binding"]]),
                               {"mode": "point", "target_type": "storage_location", "target_id": "Shelf A", **body},
                               format="json")


def test_known_pose_kinds_are_validated_and_free_form_poses_still_save():
    case = pointer_case("sp-kinds")
    assert save_pose(case, "Shelf A").status_code == 200
    assert save_pose(case, "Shelf A", {"kind": "pan_tilt", "pan_deg": 999, "tilt_deg": 0}).status_code == 400
    assert save_pose(case, "Shelf A", {"kind": "pan_tilt", "pan_deg": 1}).status_code == 400
    assert save_pose(case, "Shelf A", {"kind": "pan_tilt", "pan_deg": 1, "tilt_deg": 2, "surprise": 1}).status_code == 400
    assert save_pose(case, "Shelf A", {"kind": "teleporter", "x": 1}).status_code == 400
    assert save_pose(case, "Shelf B", {"kind": "led_segment", "strip": 0, "start": 10, "count": 4,
                                       "color": "#00ff00"}).status_code == 200
    assert save_pose(case, "Shelf B", {"kind": "led_segment", "strip": 0, "start": 10, "count": 0}).status_code == 400
    assert save_pose(case, "Shelf B", {"kind": "galvo_xy", "x": 0.25, "y": -0.5}).status_code == 200
    assert save_pose(case, "Shelf B", {"kind": "galvo_xy", "x": 2, "y": 0}).status_code == 400
    assert save_pose(case, "Shelf B", {"pan": 12.5, "tilt": -3}).status_code == 200  # no kind: free-form


def test_indicate_is_clamped_to_the_binding_caps_and_the_pointer_sees_the_clamped_values():
    case = pointer_case("sp-caps")
    assert save_pose(case, "Shelf A").status_code == 200
    assert set_caps(case, laser_max_power_pct=30, max_on_seconds=5).status_code == 200
    assert _indicate(case, duration_seconds=120).status_code == 201
    command = case["pointer"].poll_once()
    assert command["params"]["duration_seconds"] == 5
    assert command["params"]["pose"]["laser_power_pct"] == 30
    assert case["pointer"].lit and case["pointer"].power_pct == 30
    case["pointer"].tick(5)
    assert not case["pointer"].lit  # auto-clear when the on-time is over


def test_a_laser_pose_without_a_power_value_gets_the_cap_and_a_default_on_time():
    case = pointer_case("sp-defaults")
    assert save_pose(case, "Shelf A", {"kind": "pan_tilt", "pan_deg": 1, "tilt_deg": 2}).status_code == 200
    assert set_caps(case, laser_max_power_pct=40).status_code == 200
    assert _indicate(case, duration_seconds=600).status_code == 201
    params = case["pointer"].poll_once()["params"]
    assert params["pose"]["laser_power_pct"] == 40 and params["duration_seconds"] == 60  # laser default on-time cap


def test_an_led_pose_is_not_power_clamped_and_the_saved_pose_is_untouched():
    case = pointer_case("sp-led")
    led = {"kind": "led_segment", "strip": 1, "start": 0, "count": 3, "color": "green"}
    assert save_pose(case, "Shelf A", led).status_code == 200
    assert set_caps(case, laser_max_power_pct=10, max_on_seconds=20).status_code == 200
    assert _indicate(case, mode="light", duration_seconds=90).status_code == 201
    params = case["pointer"].poll_once()["params"]
    assert params["pose"] == led and params["duration_seconds"] == 20
    saved = case["client"].get(reverse("devices:admin-adapter-poses", args=[case["pointer_binding"]])).data
    assert saved[0]["pose"] == led


def test_clear_is_never_capped_and_always_allowed():
    case = pointer_case("sp-clear")
    assert save_pose(case, "Shelf A").status_code == 200
    assert set_caps(case, laser_max_power_pct=1, max_on_seconds=1).status_code == 200
    for _ in range(12):  # no rate limit on clear
        assert _indicate(case, mode="clear", target_id="").status_code == 201
    command = case["pointer"].poll_once()
    assert command["params"] == {"mode": "clear"}


def test_the_cap_fields_are_bounded_on_the_config_route():
    case = pointer_case("sp-config")
    assert set_caps(case, laser_max_power_pct=0).status_code == 400
    assert set_caps(case, laser_max_power_pct=101).status_code == 400
    assert set_caps(case, max_on_seconds=0).status_code == 400
    assert set_caps(case, max_on_seconds=601).status_code == 400
    ok = set_caps(case, laser_max_power_pct=25, max_on_seconds=8)
    assert ok.status_code == 200 and ok.data["config"] == {"laser_max_power_pct": 25, "max_on_seconds": 8}


def test_published_pose_schema_files_match_the_registry():
    import json
    from apps.devices.adapters.caps.locate_poses import POSE_KINDS
    from tests.parity_0120.adapter_api.test_registry_and_schemas import SCHEMAS
    for kind, schema in POSE_KINDS.items():
        body = json.loads((SCHEMAS / f"pose.{kind}.json").read_text(encoding="utf-8"))
        assert body["properties"] == schema["properties"] and body["required"] == schema["required"]
