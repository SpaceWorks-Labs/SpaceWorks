"""Job profile reads/estimates/actuals: no successful no-op and no module-off writes (517)."""
from decimal import Decimal

import pytest

from apps.machines.models_consumable_profiles import MachineTypeConsumable, ServiceRequestConsumableUsage
from tests.machines.eta_helpers import job
from tests.machines.member_support_cx11b_g2 import member_world
from tests.machines.route_support_cx11b_g2 import command, prove
from tests.modules.test_switch_matrix_objects_rest_isolation import rolled_back

pytestmark = [pytest.mark.django_db, pytest.mark.area_machines, pytest.mark.area_machine_service]
CASES = [("admin-machine-job-consumables", "get", "actual"),
         ("admin-machine-job-consumables", "post", "estimate"),
         ("admin-machine-job-consumables", "post", "actual"),
         ("member-machine-job-consumables", "post", "actual")]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name,method,phase", CASES)
def test_job_consumable_route_checks_service_switch_before_any_usage_write(native, name, method, phase):
    w = member_world(native)
    row = job(w, member=w.member, title="Retained consumable job")
    # Real acceptance is free with no pricing configured and emits its own baseline audit.
    from apps.machines.service_workflow import accept
    row = accept(row, w.actor, estimated_minutes=5)
    definition = MachineTypeConsumable.objects.create(makerspace=w.space, machine_type=w.kind,
        key="paper", name="Paper", unit="sheet", record_by=["staff", "member"], estimate_by="staff", required=True)
    member = name.startswith("member-")
    if not member:
        from tests.modules.switch_matrix_object_helpers import client_for
        w.client = client_for(w.actor, w.space, native)
        w.foreign = client_for(w.outsider, w.other, native)
    args = [row.pk] if member else [w.space.pk, row.pk]
    entries = [{"key": "paper", "quantity": "2"}]
    body = entries if member else {"phase": phase, "entries": entries}

    def check(response):
        if method == "get":
            assert [(r["id"], r["key"], r["name"]) for r in response.data["profile"]] == [(definition.pk, "paper", "Paper")]
            assert response.data["missing_required"] == ["paper"]
            assert response.data["actuals"] == response.data["estimates"] == []
        else:
            saved = ServiceRequestConsumableUsage.objects.get(service_request=row, definition=definition)
            assert (saved.quantity, saved.phase, saved.source, saved.key) == (Decimal("2"), phase, "member" if member else "staff", "paper")
            data = response.data if member else response.data["actuals" if phase == "actual" else "estimates"]
            assert [(r["id"], r["key"], Decimal(r["quantity"])) for r in data] == [(saved.pk, "paper", Decimal("2"))]

    audit = ("machine_service.consumables_recorded" if phase == "actual" else "machine_service.consumables_estimated",)
    callers = (w.foreign, w.same_space) if member else (w.foreign,)
    for foreign in callers:
        w.foreign = foreign
        with rolled_back():
            prove(w, "machine_service", lambda c: command(c, name, method, args, body), check,
                  audits=audit if method == "post" else ())
