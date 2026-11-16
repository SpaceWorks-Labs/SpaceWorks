"""Usage schedule HTTP behavior is a policy gate, not a fictional module route (520/526)."""
from datetime import timedelta
from decimal import Decimal

import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from django.utils import timezone

from apps.machines.models import MachineUsageEntry
from apps.maintenance.models import MaintenanceSchedule
from tests.maintenance.l16_helpers import world
from tests.maintenance.route_support_cx11b_g3 import foreign_client, foreign_refusal, prove, send
from tests.modules.switch_matrix_object_helpers import client_for

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_inventory, pytest.mark.area_machines]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("op", ["create", "patch", "list", "overdue"])
def test_meter_policy_route_effect_no_write_and_restoration(op, native):
    w = world("g3-meter-route")
    w.space.enabled_features = sorted(set(w.space.enabled_features) | {"maintenance.meters"})
    w.space.save(update_fields=["enabled_features"])
    row = MaintenanceSchedule.objects.create(machine=w.machine, description="Retained usage schedule", interval_days=30,
        next_due=timezone.localdate() + timedelta(days=30), trigger="usage", usage_hours=Decimal("1.00"),
        meter_started_at=timezone.now() - timedelta(hours=1))
    usage = MachineUsageEntry.objects.create(machine=w.machine, hours=Decimal("2.00"))
    client, outsider = client_for(w.manager, w.space, native), foreign_client(native)
    name, args, method, body = "admin-maintenance-schedule-list-create", [w.space.pk, w.machine.pk], "get", {}
    if op == "create":
        method, body = "post", {"description": "New meter", "interval_days": 14, "next_due": "2099-01-01",
                                "trigger": "usage", "usage_hours": "3.00"}
    elif op == "patch":
        name, args, method, body = "admin-maintenance-schedule-detail", [row.pk], "patch", {"usage_hours": "3.00"}
    elif op == "overdue":
        name, args = "admin-maintenance-overdue", [w.space.pk]

    def check(response):
        if op in {"create", "patch"}:
            saved = MaintenanceSchedule.objects.get(pk=response.data["id"])
            assert saved.usage_hours == Decimal("3.00") and saved.trigger == "usage"
            assert saved.description == ("New meter" if op == "create" else "Retained usage schedule")
            assert MaintenanceSchedule.objects.filter(machine=w.machine).count() == (2 if op == "create" else 1)
        else:
            records = response.data["results"] if isinstance(response.data, dict) else response.data
            assert [r["id"] for r in records] == [row.pk]
            if op == "list":
                assert records[0]["overdue"] is True

    def off_check(response):
        if op in {"create", "patch"}:
            assert response.data["trigger"].code == "invalid"
        else:
            records = response.data["results"] if isinstance(response.data, dict) else response.data
            if op == "overdue":
                assert records == []
            else:
                assert [r["id"] for r in records] == [row.pk] and records[0]["overdue"] is False

    prove(w.space, {"schedule": row, "usage": usage}, "maintenance.meters",
          lambda c: send(c or client, name, args, method, body), check,
          status=201 if op == "create" else 200,
          off=(400, None) if op in {"create", "patch"} else (200, None), off_check=off_check,
          outsiders=[(outsider, foreign_refusal(native, space_path=op != "patch"))],
          audits={"maintenance.schedule_created" if op == "create" else "maintenance.schedule_updated": 1}
          if op in {"create", "patch"} else {})

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
