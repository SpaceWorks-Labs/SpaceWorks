"""Dashboard report reads exclude unrelated history before Python materialization."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.hardware_requests.models import ReturnEvent
from apps.machines.models import MachineConsumable, MachineConsumableAdjustment, MachineServiceRequest, MachineUsageEntry, ServiceBucket
from apps.machines.models_service_consumables import ServiceRequestConsumption
from apps.machines.models_tracking import ConsumableCostRecord
from apps.operations.reports_ab_consumables import build_consumable_usage
from apps.operations.reports_ab_loans import build_loan_throughput
from tests.analytics.test_ab_consumables_m1f2 import pool
from tests.analytics.test_ab_inventory_m1f2 import enable, loan
from tests.return_helpers import make_member, make_product, make_return_evidence, make_space
from tests.test_machine_service_workflow import machine

pytestmark = pytest.mark.django_db
OLD = datetime(2020, 1, 1, tzinfo=timezone.utc)
START = datetime(2026, 10, 17, tzinfo=timezone.utc)


def test_consumption_does_not_load_historical_sources_or_costs(monkeypatch):
    space = make_space("review-consumption-bounds")
    enable(space, "machines", "machine_service")
    actor = make_member("review-bounds-reader", space)
    target = machine(space)
    stock = pool(space, target)
    bucket = ServiceBucket.objects.create(machine=target, name="Queue")
    material = MachineConsumable.objects.create(machine=target, measurement="grams", label="Powder")
    forbidden = {}
    for at in (OLD, START):
        with patch("django.utils.timezone.now", return_value=at):
            manual = MachineUsageEntry.objects.create(machine=target, hours=1)
            adjustment = MachineConsumableAdjustment.objects.create(makerspace=space, consumable_pool=stock,
                kind="manual", usage_entry=manual, quantity_delta=-2)
            job = MachineServiceRequest.objects.create(makerspace=space, bucket=bucket, assigned_machine=target,
                requester=actor, title="Finalized", status="completed", completed_at=at,
                run_consumable_pool=stock, actual_consumed_quantity=3)
            held = MachineServiceRequest.objects.create(makerspace=space, bucket=bucket, assigned_machine=target,
                requester=actor, title="Reserved", status="in_progress", started_at=at,
                run_consumable_pool=stock, reserved_quantity=5)
            consumption = ServiceRequestConsumption.objects.create(service_request=job, machine_consumable=material,
                measurement="grams", quantity=4, outcome="completed")
        # Costs may be recorded later than the report window: selection follows source identity.
        for kind, source_id, quantity in (("manual_adjustment", adjustment.pk, 2),
                                          ("pooled_service", job.pk, 3), ("non_pool_consumption", consumption.pk, 4)):
            with patch("django.utils.timezone.now", return_value=START + timedelta(days=2)):
                cost = ConsumableCostRecord.objects.create(makerspace=space, source_kind=kind, source_id=source_id,
                    quantity=quantity, measurement_unit="grams", unit_price_minor_per_measurement_unit=3,
                    cost_total_minor=quantity * 3, currency="USD")
            if at == OLD:
                forbidden.setdefault(ConsumableCostRecord, set()).add(cost.pk)
        if at == OLD:
            forbidden.update({MachineConsumableAdjustment: {adjustment.pk},
                MachineServiceRequest: {job.pk, held.pk}, ServiceRequestConsumption: {consumption.pk}})

    def guard(model, ids):
        original = model.from_db

        def from_db(cls, db, names, values):
            instance = original(db, names, values)
            assert instance.pk not in ids, f"Historical {model.__name__} was materialized"
            return instance

        monkeypatch.setattr(model, "from_db", classmethod(from_db))

    for model, ids in forbidden.items():
        guard(model, ids)
    rows = build_consumable_usage(space.pk, actor=actor, date_range=(START, START + timedelta(days=1))).records
    assert sum(row["consumed_quantity"] for row in rows) == 9
    assert sum(row["reserved_quantity"] for row in rows) == 5
    assert sum(row["cost_total_minor"] for row in rows) == 27


def test_return_history_is_limited_to_selected_requests_without_losing_prior_partial_returns():
    space = make_space("review-return-bounds")
    enable(space, "request_workflow")
    actor = make_member("review-returns-reader", space)
    selected = loan(space, actor, make_product(space), at=OLD, returned=3)
    unrelated = loan(space, actor, make_product(space, name="Unrelated"), at=OLD, returned=99)
    for request, at in ((unrelated, OLD), (selected, OLD), (selected, START)):
        with patch("django.utils.timezone.now", return_value=at):
            ReturnEvent.objects.create(makerspace=space, request=request, actor=actor,
                evidence=make_return_evidence(space, actor), remark="Partial return")
    with CaptureQueriesContext(connection) as captured:
        rows = build_loan_throughput(space.pk, date_range=(START, START + timedelta(days=1))).records
    assert sum(row["return_events"] for row in rows) == 1
    assert sum(row["return_quantity_unknown_events"] for row in rows) == 1
    assert sum(row["returned_units"] for row in rows) == 0
    counts = [query["sql"] for query in captured if 'COUNT(' in query["sql"] and 'hardware_requests_returnevent' in query["sql"]]
    assert len(counts) == 1
    # The count includes earlier returns only for requests present in the selected window.
    assert ' IN (SELECT ' in counts[0] and '2026-10-17' in counts[0] and '2026-10-18' in counts[0]
