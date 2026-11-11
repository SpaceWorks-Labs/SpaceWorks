"""Machine integrations are OFF by default: every new route answers 404, nothing is stored."""
import uuid

import pytest
from django.urls import reverse

from apps.devices.models import MachineTypeIntegration, PrinterStatusSnapshot
from apps.makerspaces.capabilities import FEATURES
from tests.devices.sim_agent import integrated_case, snapshot, started_request

pytestmark = pytest.mark.django_db(transaction=True)


def test_the_capability_is_a_machines_feature_off_by_default_and_hidden_from_the_console():
    feature = FEATURES["machines.integrations"]
    assert (feature.parent_module, feature.default_enabled, feature.frontend_exposed) == ("machines", False, False)
    assert set(feature.requires_modules) == {"devices", "machine_service"}


def test_every_route_is_404_while_the_capability_is_off():
    case = integrated_case("int-off", enabled=False)
    row = started_request(case)
    agent, client, space = case["agent"], case["client"], case["space"]
    assert agent.queue().status_code == 404
    assert agent.report(row.pk, event="started", external_job_id="x-1").status_code == 404
    type_id = case["machine"].machine_type_id
    lst = reverse("devices:admin-machine-type-integration-list", args=[space.pk, type_id])
    status = reverse("devices:admin-machine-type-integration-status", args=[space.pk, type_id])
    assert client.get(lst).status_code == 404
    assert client.post(lst, {"kind": "printer_agent"}, format="json").status_code == 404
    assert client.get(status).status_code == 404
    detail = reverse("devices:admin-machine-type-integration-detail", args=[MachineTypeIntegration.objects.get().pk])
    assert client.get(detail).status_code == 404
    assert client.patch(detail, {"enabled": False}, format="json").status_code == 404
    assert client.delete(detail).status_code == 404
    assert client.get(reverse("devices:admin-machine-type-integration-detail", args=[uuid.uuid4()])).status_code == 404


def test_a_heartbeat_still_works_and_stores_no_snapshot_while_off():
    case = integrated_case("int-off-heartbeat", enabled=False)
    plain = case["agent"].heartbeat()
    assert plain.status_code == 200 and "status_snapshot" not in plain.data
    response = case["agent"].heartbeat(snapshot())
    assert response.status_code == 200 and response.data["status_snapshot"] == "not_integrated"
    assert not PrinterStatusSnapshot.objects.exists()


def test_a_disabled_type_binding_is_the_same_as_off():
    case = integrated_case("int-disabled-binding")
    MachineTypeIntegration.objects.update(enabled=False)
    assert case["agent"].queue().status_code == 404
    assert case["agent"].heartbeat(snapshot()).data["status_snapshot"] == "not_integrated"
