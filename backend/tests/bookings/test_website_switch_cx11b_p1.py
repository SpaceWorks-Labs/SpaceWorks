"""Retained resource website on browser and native, including its parent module."""
import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from django.urls import reverse

from tests.inventory.switch_support_cx11b_p1 import prove_route, staff_outsiders
from tests.modules.switch_matrix_object_helpers import object_world

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_bookings]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["bookings", "bookings.website"])
def test_website_switch_retains_the_same_editor_page(key, native):
    space, client, objects = object_world(native)
    url = reverse("admin-booking-website", kwargs={"pk": objects["room"].pk})
    prove_route(space, client, objects, key, lambda c: c.get(url),
                off=(404, "module_disabled" if key == "bookings" else "feature_disabled"), outsiders=staff_outsiders(native))

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
