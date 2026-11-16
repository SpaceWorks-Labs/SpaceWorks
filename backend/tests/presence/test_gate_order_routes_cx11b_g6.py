"""517 regression: an off geofence must refuse before lazy domain provisioning.

Product bug reported to the orchestrator; G6 may change only notifications product code.
"""
import pytest
from django.urls import reverse

from apps.presence.models import PresenceSettings
from tests.modules.switch_matrix_object_helpers import response_pair
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, switch
from tests.notifications.routes_support_cx11b_g6 import snapshot, world
from tests.presence.fence_helpers import fence

pytestmark = [pytest.mark.django_db, pytest.mark.area_presence]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
def test_geofence_off_refuses_before_lazy_settings_insert(native):
    space, actor, client, stranger, foreign = world(native)
    fence(space)
    assert not PresenceSettings.objects.filter(makerspace=space).exists()
    switch(space, "presence.geofence")
    before = snapshot()
    with no_domain_writes():
        response = client.post(reverse("presence-start", kwargs={"makerspace_slug": space.slug}),
            {"duration_minutes": 60, "latitude": 0, "longitude": 0, "accuracy": 5}, format="json")
    assert response_pair(response) == (400, "geofence_unconfigured")
    assert snapshot() == before
