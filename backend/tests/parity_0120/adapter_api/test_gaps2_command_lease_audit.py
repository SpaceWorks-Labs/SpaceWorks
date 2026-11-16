"""Decision 337a/b: a command lease is audited (without token or params); the safety sweep runs in a read-only space."""
import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.audit.presentation_catalog import PRESENTATION_CATALOG
from apps.tenant_migration.audit_references_adapter import EDGES
from tests.parity_0120.adapter_api.adapter_case import adapter_case

pytestmark = pytest.mark.django_db(transaction=True)


def test_leasing_a_command_writes_one_audit_row_with_ids_only():
    case = adapter_case("gaps2-lease")
    url = reverse("devices:admin-adapter-binding-command", args=[case["binding_id"]])
    queued = case["client"].post(url, {"capability": "control", "command": "pause", "params": {}}, format="json")
    assert queued.status_code == 201, queued.data
    leased = case["sim"].post("commands/lease").data["command"]
    row = AuditLog.objects.get(action="devices.adapter_command_leased")
    assert row.actor_id is None  # a device is never the actor
    assert row.meta["command_id"] == leased["command_id"] and row.meta["command"] == "pause"
    assert row.meta["attempt"] == 1 and row.meta["capability"] == "control"
    assert leased["lease_token"] not in str(row.meta) and "params" not in row.meta
    case["sim"].post("commands/lease")  # nothing left to lease: no second row
    assert AuditLog.objects.filter(action="devices.adapter_command_leased").count() == 1


def test_the_lease_action_is_catalogued_and_its_ids_are_declared():
    assert "devices.adapter_command_leased" in PRESENTATION_CATALOG
    assert ("devices.adapter_command_leased", "device_id") in EDGES
    assert ("devices.adapter_command_leased", "command_id") in EDGES


def test_the_safety_sweep_is_allowed_in_a_read_only_space():
    from apps.space_controls.write_policy import READ_ONLY_OPERATIONS
    assert "devices.adapter_safety" in READ_ONLY_OPERATIONS
