"""Recorded service duration and independent manual consumption survive source gates."""

from decimal import Decimal

import pytest

from apps.machines.models import MachineConsumableAdjustment, MachineServiceRequest, MachineUsageEntry, ServiceBucket
from apps.machines.models_tracking import ConsumableCostRecord
from tests.analytics.test_ab_consumables_m1f2 import pool
from tests.analytics.test_ab_inventory_m1f2 import enable
from tests.analytics.test_j_measurements_m1f2 import machine, platform_actor, usage
from tests.return_helpers import make_space
from django.utils import timezone

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("status", ["failed", "completed", "collected"])
def test_platform_terminal_hours_use_actual_duration(status):
    space, actor = make_space("review-platform-hours"), platform_actor()
    enable(space, "machines", "machine_service")
    target = machine(space, "meter")
    bucket = ServiceBucket.objects.create(machine=target, name="Queue")
    MachineServiceRequest.objects.create(makerspace=space, bucket=bucket, assigned_machine=target,
        requester=actor, title="Job", status=status, actual_minutes=70, estimated_minutes=120,
        fail_percent_complete=25, failed_at=timezone.now() if status == "failed" else None,
        completed_at=timezone.now() if status != "failed" else None)
    rows = [r for r in usage(actor)["typed_rows"] if r["metric"] == "service_machine_hours"]
    assert len(rows) == 1
    # 70 actual minutes = 1.1667 h. The JSON projection formats decimals as fixed-point text with a third
    # place when one is present (the money formatter, 1.167); the point is actual (70), not estimate (120) or 25%.
    assert abs(Decimal(rows[0]["value"]) - Decimal(70) / 60) < Decimal("0.005")


@pytest.mark.parametrize("service_enabled", [True, False])
def test_manual_usage_and_cost_survive_machine_service_off(service_enabled):
    space, actor = make_space("review-platform-manual"), platform_actor()
    enable(space, "machines", "machine_service")
    target = machine(space, "meter")
    stock = pool(space, target)
    manual = MachineUsageEntry.objects.create(machine=target, hours=1)
    adjustment = MachineConsumableAdjustment.objects.create(makerspace=space, consumable_pool=stock,
        kind="manual", usage_entry=manual, quantity_delta=-5)
    ConsumableCostRecord.objects.create(makerspace=space, source_kind="manual_adjustment", source_id=adjustment.pk,
        quantity=5, measurement_unit="grams", unit_price_minor_per_measurement_unit=3,
        cost_total_minor=15, currency="USD")
    # Retained service facts must be hidden on disable, while independent facts remain.
    bucket = ServiceBucket.objects.create(machine=target, name="Queue")
    job = MachineServiceRequest.objects.create(makerspace=space, bucket=bucket, assigned_machine=target,
        requester=actor, title="Job", status="completed", completed_at=timezone.now(),
        run_consumable_pool=stock, actual_consumed_quantity=20, actual_consumed_grams=20)
    ConsumableCostRecord.objects.create(makerspace=space, source_kind="pooled_service", source_id=job.pk,
        quantity=20, measurement_unit="grams", unit_price_minor_per_measurement_unit=3,
        cost_total_minor=60, currency="USD")
    if not service_enabled:
        space.enabled_modules.remove("machine_service")
        space.save(update_fields=["enabled_modules"])
    rows = usage(actor)["typed_rows"]
    assert sum(Decimal(r["value"]) for r in rows if r["metric"] == "consumables") == (25 if service_enabled else 5)
    assert sum(r["value"] for r in rows if r["metric"] == "consumable_cost") == (75 if service_enabled else 15)
