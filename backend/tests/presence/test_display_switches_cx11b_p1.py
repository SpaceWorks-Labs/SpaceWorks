"""Retained display/player configuration and hard self-check-in geofence policy."""
import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from django.urls import reverse
from django.utils import timezone

from apps.presence.models_display import DisplayScreen
from apps.presence.models_anthias import AnthiasPlayer
from tests.inventory.switch_support_cx11b_p1 import prove_route
from tests.modules.switch_matrix_object_helpers import object_world

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_presence]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("kind,key", [("screen", "presence"), ("screen", "presence.public_display"),
                                      ("player", "display.anthias_push"), ("player", "presence")])
def test_display_switches_keep_the_same_screen_and_player(kind, key, native):
    space, client, objects = object_world(native)
    screen = DisplayScreen.objects.create(makerspace=space, name="Retained TV", token_digest="a" * 64,
        code_expires_at=timezone.now(), claimed_at=timezone.now(), panels=["announcement"])
    player = AnthiasPlayer.objects.create(makerspace=space, name="Retained player", host_url="http://192.168.1.20")
    objects.update(screen=screen, player=player)
    if kind == "player":
        url = reverse("admin-anthias-player", kwargs={"makerspace_id": space.pk, "pk": player.pk})
        call = lambda c: c.patch(url, {"name": "Updated player"}, format="json")
        off = (404, "not_found" if key == "presence" else "feature_disabled")
    else:
        url = reverse("admin-presence-display-detail", kwargs={"makerspace_id": space.pk, "pk": screen.pk})
        call = lambda c: c.patch(url, {"name": "Updated TV"}, format="json")
        off = (404, "not_found")
    prove_route(space, client, objects, key, call, off=off)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key,off", [("presence.geofence", (400, "geofence_unconfigured")),
                                     ("presence", (404, "not_found"))])
def test_geofence_off_refuses_self_checkin_without_changing_existing_rows(key, off, native):
    space, client, objects = object_world(native)
    space.geofence_enabled = True
    space.geofence_latitude = space.geofence_longitude = 0
    space.geofence_radius_m = 100
    space.save(update_fields=["geofence_enabled", "geofence_latitude", "geofence_longitude", "geofence_radius_m"])
    url = reverse("presence-start", kwargs={"makerspace_slug": space.slug})
    body = {"duration_minutes": 60, "latitude": 0, "longitude": 0, "accuracy": 5}
    prove_route(space, client, objects, key, lambda c: c.post(url, body, format="json"), off=off, on=(201, None))

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
