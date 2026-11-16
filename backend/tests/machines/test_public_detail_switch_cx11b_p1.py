"""Public machine detail retains the same opted-in machine through off/on."""
import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from django.urls import reverse

from tests.inventory.switch_support_cx11b_p1 import prove_route
from tests.modules.switch_matrix_object_helpers import object_world

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_machines]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["machines", "machines.public_detail"])
def test_public_machine_detail_restores_the_same_public_machine(key, native):
    space, client, objects = object_world(native)
    machine = objects["machine"]
    machine.is_public = True
    machine.save(update_fields=["is_public"])
    space.public_site_enabled = True
    space.save(update_fields=["public_site_enabled"])
    url = reverse("public-machine-detail", kwargs={"makerspace_slug": space.slug, "pk": machine.pk})
    prove_route(space, client, objects, key, lambda c: c.get(url),
                off=(404, "module_disabled" if key == "machines" else "feature_disabled"),
                check=lambda r: _same_machine(r, machine))


def _same_machine(response, machine):
    assert response.data["id"] == machine.pk
    assert response.data["name"] == machine.name

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
