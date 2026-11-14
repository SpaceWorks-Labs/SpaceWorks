"""Machine quota admission is identical for browser and attested staff grants."""
import pytest
from django.urls import reverse

from apps.machines.models import Machine, MachineType
from tests.return_helpers import authenticated_client, make_member, make_space
from tests.shop.test_native_shop_limits_cx7 import native_staff_client

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("suffix", ["", ".space-works.tech"])
def test_machine_last_slot_and_next_refusal_keep_existing_rows(surface, suffix, settings, monkeypatch):
    settings.PLATFORM_DOMAIN_SUFFIX = suffix
    settings.INFRA_HOSTS = {"testserver"}
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("cx7-machine-boundary")
    if surface == "browser":
        actor = make_member("cx7-machine-manager", space)
        caller = authenticated_client(actor)
    else:
        caller, actor = native_staff_client(space, surface, settings, monkeypatch, host="testserver")
    caller.defaults["HTTP_HOST"] = "testserver"
    machine_type = MachineType.objects.create(makerspace=space, slug="quota-tool", name="Quota tool")
    space.resource_limit_overrides = {"machines": 1}
    space.save(update_fields=["resource_limit_overrides"])
    url = reverse("admin-machines", kwargs={"makerspace_id": space.pk})
    body = {"machine_type_id": machine_type.pk, "name": "Last machine"}
    maximum = caller.post(url, body, format="json")
    assert maximum.status_code == 201
    refused = caller.post(url, {**body, "name": "Excess machine"}, format="json")
    assert refused.status_code == 400
    assert refused.json()["code"] == "limit_reached"
    assert refused.json()["detail"] == refused.json()["limit"]
    assert list(Machine.objects.filter(makerspace=space).values_list("name", flat=True)) == ["Last machine"]
    space.resource_limit_overrides = {"machines": 2}
    space.save(update_fields=["resource_limit_overrides"])
    restored = caller.post(url, {**body, "name": "Excess machine"}, format="json")
    assert restored.status_code == 201
    assert Machine.objects.filter(makerspace=space).count() == 2
