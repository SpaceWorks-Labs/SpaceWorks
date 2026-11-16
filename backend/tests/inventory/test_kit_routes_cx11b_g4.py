"""Each equipment template route proves immutable versions or a changed publication flag."""
import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.inventory.equipment_kit_services import create_template
from apps.inventory.models_equipment_proposals import EquipmentKitTemplate, EquipmentKitVersion
from tests.modules.switch_matrix_object_helpers import object_world
from tests.operations.route_support_cx11b_g4 import contains, cycle, outsider, send
from tests.return_helpers import make_product

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_lending]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name,method", [("hardware_requests:equipment-kit-list", "GET"), ("hardware_requests:equipment-kit-list", "POST"),
    ("hardware_requests:equipment-kit-detail", "GET"), ("hardware_requests:equipment-kit-version", "POST"),
    ("hardware_requests:equipment-kit-publication", "POST"), ("hardware_requests:equipment-kit-archive", "POST")])
def test_staff_kit_route_effect_and_retention(native, name, method):
    space, client, _ = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    product = make_product(space)
    lines = [{"product_id": product.pk, "kind": "returnable", "quantity_per_person": 1}]
    template, version = create_template(actor=actor, makerspace_id=space.pk, name="Retained kit", lines=lines)
    lines = version.lines
    kwargs = {"makerspace_id": space.pk}
    if name != "hardware_requests:equipment-kit-list":
        kwargs["kit_id"] = template.pk
    url = reverse(name, kwargs=kwargs)
    body, action = {}, ()
    if method == "POST":
        if name == "hardware_requests:equipment-kit-list":
            body, action = {"name": "New kit", "lines": lines}, ("inventory.equipment_kit_created",)
        elif name.endswith("version"):
            body = {"expected_revision": 1, "name": "Version two", "lines": lines}
            action = ("inventory.equipment_kit_version_created",)
        else:
            body = {"expected_revision": 1, "archived" if name.endswith("archive") else "published_for_contexts": True}
            action = ("inventory.equipment_kit_changed",)

    def check(response):
        template.refresh_from_db()
        assert EquipmentKitVersion.objects.get(pk=version.pk).lines == lines
        if name == "hardware_requests:equipment-kit-list" and method == "GET":
            contains(response, template.pk)
            assert response.data["results"][0]["name"] == "Retained kit"
        elif name == "hardware_requests:equipment-kit-list":
            created = EquipmentKitTemplate.objects.get(pk=response.data["id"])
            assert (created.name, created.current_version, created.revision) == ("New kit", 1, 1)
            assert created.versions.get().lines == lines
            assert EquipmentKitTemplate.objects.filter(makerspace=space).count() == 2
        elif name.endswith("detail"):
            assert (response.data["id"], response.data["lines"]) == (template.pk, lines)
        elif name.endswith("version"):
            assert (template.name, template.current_version, template.revision) == ("Version two", 2, 2)
            assert list(template.versions.order_by("version").values_list("version", "lines")) == [(1, lines), (2, lines)]
        else:
            flag = "archived" if name.endswith("archive") else "published_for_contexts"
            assert getattr(template, flag) is True
            assert (template.revision, template.current_version) == (2, 1)
    foreign = outsider(native)
    cycle(space, "staff_admin", lambda: send(client, method, url, body), check,
          on=(201 if method == "POST" and name in {"hardware_requests:equipment-kit-list", "hardware_requests:equipment-kit-version"} else 200, None),
          off=(404, "module_disabled"), refusal_key="staff_admin", audit=action,
          foreign=lambda: send(foreign, method, url, body), foreign_native=native)
