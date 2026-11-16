"""The browser/native credential surface follows the same access child as signed decisions."""
import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from django.urls import reverse

from apps.devices.services_adapter_credentials import set_credential
from tests.inventory.switch_support_cx11b_p1 import prove_route, staff_outsiders
from tests.modules.switch_matrix_object_helpers import client_for
from tests.parity_0120.adapter_api.adapter_case import adapter_case, plain_member

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_machines, pytest.mark.area_devices]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["machines.integrations.access", "machines.integrations", "machines", "devices", "machine_service"])
def test_access_credentials_switch_retains_the_same_private_digest(key, native):
    case = adapter_case("p1-access-credential")
    member = plain_member("p1-access-credential-member", case["space"])
    row = set_credential(case["manager"], case["space"].pk, member.pk, "nfc", "04A1B2C3D4")
    path = reverse("devices:admin-adapter-credentials", args=[case["space"].pk])
    prove_route(case["space"], client_for(case["manager"], case["space"], native),
                {"credential": row, "device": case["device"]}, key, lambda c: c.get(path), off=(404, "not_found"),
                check=lambda r: _same_credential(r, row), outsiders=staff_outsiders(native))


def _same_credential(response, row):
    assert [str(item["id"]) for item in response.data] == [str(row.pk)]
    assert "04A1B2C3D4" not in str(response.data)
    assert row.digest not in str(response.data)

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
