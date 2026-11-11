"""Staff bind an integration kind to a machine type (created disabled), audited, scoped."""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.devices.models import MachineTypeIntegration
from apps.machines.printer_capabilities import resolve_global_printer_type
from tests.devices.sim_agent import enable_integrations, integrated_case, snapshot

pytestmark = pytest.mark.django_db(transaction=True)


def _printer_type():
    from apps.machines.models import MachineType
    from apps.machines.printer_capabilities import PRINTER_CONFIG, PRINTER_SLUG
    return resolve_global_printer_type() or MachineType.objects.create(
        slug=PRINTER_SLUG, name="3D printer", is_builtin=True, capability_config=PRINTER_CONFIG)


def test_bind_update_and_unbind_the_printer_type_are_audited():
    case = integrated_case("int-bind", bind_type=False)
    printer = _printer_type()
    url = reverse("devices:admin-machine-type-integration-list", args=[case["space"].pk, printer.pk])
    created = case["client"].post(url, {"kind": "printer_agent"}, format="json")
    assert created.status_code == 201, created.data
    assert created.data["enabled"] is False and created.data["config_schema_version"] == 1
    assert case["client"].post(url, {"kind": "printer_agent"}, format="json").status_code == 409
    assert [row["id"] for row in case["client"].get(url).data] == [created.data["id"]]
    detail = reverse("devices:admin-machine-type-integration-detail", args=[created.data["id"]])
    assert case["client"].patch(detail, {"enabled": True}, format="json").data["enabled"] is True
    assert case["client"].patch(detail, {"price": 1}, format="json").status_code == 400
    assert case["client"].delete(detail).status_code == 204
    actions = list(AuditLog.objects.filter(action__startswith="devices.integration_").order_by("pk")
                   .values_list("action", flat=True))
    assert actions == ["devices.integration_bound", "devices.integration_updated", "devices.integration_unbound"]
    assert AuditLog.objects.get(action="devices.integration_bound").meta["machine_type_id"] == printer.pk


def test_a_printer_agent_only_binds_the_printer_type():
    case = integrated_case("int-bind-kind", bind_type=False)
    url = reverse("devices:admin-machine-type-integration-list",
                  args=[case["space"].pk, case["machine"].machine_type_id])
    response = case["client"].post(url, {"kind": "printer_agent"}, format="json")
    assert response.status_code == 400 and not MachineTypeIntegration.objects.exists()


def test_staff_without_manage_devices_are_refused_and_the_superadmin_is_not():
    from apps.accounts.models import User
    from tests.return_helpers import make_user
    case = integrated_case("int-bind-scope")
    url = reverse("devices:admin-machine-type-integration-list",
                  args=[case["space"].pk, case["machine"].machine_type_id])
    stranger = APIClient()
    stranger.force_authenticate(make_user("int-bind-stranger"))
    assert stranger.get(url).status_code in (403, 404)
    root = APIClient()
    root.force_authenticate(User.objects.create_superuser("int-root", email="root@int.test", password="x" * 20))
    assert root.get(url).status_code == 200


def test_the_status_list_shows_the_latest_snapshot_read_only():
    case = integrated_case("int-status")
    assert case["agent"].heartbeat(snapshot()).data["status_snapshot"] == "stored"
    url = reverse("devices:admin-machine-type-integration-status",
                  args=[case["space"].pk, case["machine"].machine_type_id])
    rows = case["client"].get(url).data
    assert len(rows) == 1 and rows[0]["device_id"] == str(case["device"].pk)
    assert rows[0]["snapshot"]["state"] == "printing" and rows[0]["snapshot"]["progress_percent"] == 42
    assert case["client"].post(url, {}, format="json").status_code == 405


def test_another_spaces_type_is_not_reachable():
    case = integrated_case("int-bind-other")
    other = integrated_case("int-bind-other-2")
    enable_integrations(other["space"])
    url = reverse("devices:admin-machine-type-integration-list",
                  args=[case["space"].pk, other["machine"].machine_type_id])
    assert case["client"].get(url).status_code == 404
