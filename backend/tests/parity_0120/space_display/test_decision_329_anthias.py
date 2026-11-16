"""Decision 329 (d): the Anthias routes answer the typed `feature_disabled` 404 like every other gate."""
import pytest

pytestmark = pytest.mark.django_db
HOST = "http://192.168.1.20"


def _admin(space, tail=""):
    return f"/api/v1/admin/makerspace/{space.pk}/{tail}"


def _off(space, key):
    space.enabled_features = [feature for feature in space.enabled_features if feature != key]
    space.save(update_fields=["enabled_features"])


def test_player_routes_answer_the_typed_404_while_anthias_push_is_off(lane):
    admin = lane.client(lane.staff)
    for response in (
        admin.post(_admin(lane.space, "anthias-players"), {"name": "x", "host_url": HOST}, format="json"),
        admin.patch(_admin(lane.space, "anthias-players/987654"), {"name": "y"}, format="json"),
        admin.delete(_admin(lane.space, "anthias-players/987654")),
        admin.post(_admin(lane.space, "anthias-players/987654/test")),
        admin.post(_admin(lane.space, "anthias-players/987654/sync")),
    ):
        assert response.status_code == 404
        assert response.data == {"detail": "display.anthias_push is turned off for this makerspace.",
                                 "code": "feature_disabled", "feature": "display.anthias_push"}


def test_the_player_list_reports_the_switch_instead_of_refusing(lane):
    response = lane.client(lane.staff).get(_admin(lane.space, "anthias-players"))
    assert response.status_code == 200 and response.data["enabled"] is False and response.data["players"] == []


def test_screen_players_answer_the_typed_404_while_display_screens_are_off(lane):
    lane.space.enabled_features = sorted(set(lane.space.enabled_features) | {"display.anthias_push"})
    lane.space.save(update_fields=["enabled_features"])
    _off(lane.space, "presence.public_display")

    response = lane.client(lane.staff).put(_admin(lane.space, "presence-displays/987654/players"),
                                           {"player_ids": []}, format="json")

    assert response.status_code == 404
    assert response.data["code"] == "feature_disabled" and response.data["feature"] == "presence.public_display"
