from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import DatabaseError, connection, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.machines import services, role_scope
from apps.machines.consumable_costs import record_cost
from apps.machines.models import MachineConsumable, MachineConsumableAdjustment, MachineUsageEntry
from apps.machines.models_tracking import MachineStatusEvent, ConsumableCostRecord
from apps.machines.service_consumable_pools import create_pool, log_typed_manual_usage
from apps.machines.service_workflow import accept, start, complete, fail
from apps.maintenance.services_shared import apply_idle_transition
from tests.return_helpers import make_member, make_product, make_space
from tests.test_machine_service_workflow import machine, request

pytestmark = pytest.mark.django_db


def member_account(username, space):
    """Usage attribution names a member account (account kinds), never staff."""
    return make_member(username, space, membership_role="member", role="requester")


def test_every_status_writer_records_real_edges_once():
    space = make_space("status-writers")
    actor = make_member("status-writers-manager", space)
    target = machine(space)
    services.set_status(target, actor, "maintenance")
    services.set_status(target, actor, "maintenance")
    target.refresh_from_db()
    apply_idle_transition(target, actor)
    row = request(space, actor=actor, target=target)
    accept(row, actor)
    start(row, actor, role_scope.EXEMPT, machine_id=target.pk)
    complete(row, actor, actual_minutes=1, consumptions=[])
    services.retire_machine(target, actor)
    events = list(MachineStatusEvent.objects.filter(machine=target).order_by("at", "pk"))
    assert [(e.from_status, e.to_status, e.source) for e in events] == [
        ("idle", "maintenance", "manual"), ("maintenance", "idle", "maintenance"),
        ("idle", "running", "service_start"), ("running", "idle", "service_release"),
        ("idle", "offline", "retire"),
    ]
    assert all(e.makerspace_id == space.pk for e in events)
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("UPDATE machines_machinestatusevent SET source = 'changed' WHERE id = %s", [events[0].pk])


@pytest.mark.parametrize("outcome,actual", [("complete", "10"), ("fail", "4")])
def test_service_cost_finalizes_even_when_reservation_needs_no_adjustment(outcome, actual):
    space = make_space("service-cost-" + outcome)
    actor = make_member("service-cost-user-" + outcome, space)
    target = machine(space)
    pool = create_pool(space, actor, material="Material", initial_grams=100,
                       unit_cost=Decimal("20"), cost_currency="USD", cost_unit="kg")
    row = request(space, actor=actor, target=target)
    accept(row, actor)
    start(row, actor, role_scope.EXEMPT, machine_id=target.pk, consumable_pool_id=pool.pk, planned_grams=Decimal("10"))
    assert not ConsumableCostRecord.objects.exists()
    if outcome == "complete":
        complete(row, actor, actual_minutes=5, consumptions=[], actual_grams=Decimal(actual))
        assert not MachineConsumableAdjustment.objects.filter(kind="reconcile").exists()
    else:
        fail(row, actor, reason="Failed", percent_complete=40, actual_minutes=2, consumptions=[], actual_grams=Decimal(actual))
    cost = ConsumableCostRecord.objects.get(source_kind="pooled_service", source_id=row.pk)
    assert cost.quantity == Decimal(actual) and cost.measurement_unit == "grams"
    assert cost.unit_price_minor_per_measurement_unit == Decimal("2")
    assert cost.cost_total_minor == int(actual) * 2 and cost.currency == "USD"
    assert MachineStatusEvent.objects.filter(machine=target, source="service_release").count() == 1


def test_manual_usage_is_attributed_and_costs_only_manual_adjustments():
    space = make_space("manual-cost")
    actor, member = make_member("manual-manager", space), member_account("manual-member", space)
    target = machine(space)
    pool = create_pool(space, actor, material="Liquid", quantity=2000, unit="milliliters",
                       unit_cost=Decimal("8"), cost_currency="USD", cost_unit="liters")
    started_at = timezone.now() - timedelta(hours=1)
    entry = log_typed_manual_usage(target, actor, duration_minutes=10, outcome="success", percent_complete=100,
                                  quantity=250, pool=pool, member=member.pk, started_at=started_at)
    assert entry.member_id == member.pk and entry.started_at == started_at
    adjustment = MachineConsumableAdjustment.objects.get(usage_entry=entry)
    cost = ConsumableCostRecord.objects.get(source_kind="manual_adjustment", source_id=adjustment.pk)
    assert cost.quantity == 250 and cost.unit_price_minor_per_measurement_unit == Decimal("0.8")
    assert cost.cost_total_minor == 200
    pool.unit_cost = Decimal("8000")
    assert record_cost(makerspace=space, source_kind="manual_adjustment", source_id=adjustment.pk,
        quantity=250, measurement_unit="milliliters", price_source=pool, actor=actor).pk == cost.pk
    assert ConsumableCostRecord.objects.count() == 1
    cost.refresh_from_db()
    assert cost.cost_total_minor == 200
    from apps.machines.service_consumable_pools import correct_pool
    correct_pool(pool, actor, quantity_delta=1, reason="Recount")
    assert ConsumableCostRecord.objects.count() == 1


def test_non_pool_product_cost_and_gram_consumption_without_price():
    space = make_space("nonpool-cost")
    actor = make_member("nonpool-manager", space)
    target = machine(space)
    product = make_product(space, unit_cost=Decimal("1.25"), cost_currency="USD", cost_unit="count")
    count = MachineConsumable.objects.create(machine=target, product=product, measurement="count")
    grams = MachineConsumable.objects.create(machine=target, label="Unpriced powder", measurement="grams", remaining=100)
    row = request(space, actor=actor, target=target)
    accept(row, actor)
    start(row, actor, role_scope.EXEMPT, machine_id=target.pk)
    complete(row, actor, actual_minutes=1, consumptions=[
        {"machine_consumable_id": count.pk, "quantity": 2},
        {"machine_consumable_id": grams.pk, "quantity": 5},
    ])
    assert row.consumptions.count() == 2
    cost = ConsumableCostRecord.objects.get()
    assert cost.source_kind == "non_pool_consumption" and cost.quantity == 2
    assert cost.unit_price_minor_per_measurement_unit == 125 and cost.cost_total_minor == 250


@pytest.mark.parametrize("currency,expected", [("JPY", 1), ("KWD", 1000)])
def test_cost_uses_currency_minor_unit_exponent(currency, expected):
    space = make_space("currency-" + currency.lower())
    pool = create_pool(space, None, material="Material", quantity=1, unit="count",
                       unit_cost=Decimal(1), cost_currency=currency, cost_unit="count")
    row = record_cost(makerspace=space, source_kind="manual_adjustment", source_id=1,
                      quantity=1, measurement_unit="count", price_source=pool)
    assert row.cost_total_minor == expected


def test_manual_member_must_be_active_local_and_new_columns_remain_immutable():
    space, other = make_space("usage-local"), make_space("usage-foreign")
    actor, outsider = make_member("usage-actor", space), member_account("usage-outsider", other)
    target = machine(space)
    with pytest.raises(ValidationError):
        services.log_usage(target, actor, Decimal(1), member=outsider.pk)
    member = member_account("usage-inactive", space)
    member.makerspace_memberships.update(status="revoked")
    with pytest.raises(ValidationError):
        services.log_usage(target, actor, Decimal(1), member=member.pk)
    # Staff accounts are never usage members, even in their own makerspace.
    with pytest.raises(ValidationError):
        services.log_usage(target, actor, Decimal(1), member=actor.pk)
    local = member_account("usage-local-member", space)
    when = timezone.now() - timedelta(minutes=30)
    entry = services.log_usage(target, actor, Decimal(1), member=local, started_at=when)
    assert (entry.member_id, entry.started_at) == (local.pk, when)
    assert MachineUsageEntry._meta.get_field("member").remote_field.on_delete.__name__ == "SET_NULL"
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("UPDATE machines_machineusageentry SET started_at = NULL WHERE id = %s", [entry.pk])


def test_usage_candidate_picker_is_scoped_and_excludes_revoked_members():
    from tests.return_helpers import authenticated_client
    space, foreign = make_space("picker-local"), make_space("picker-foreign")
    actor = make_member("picker-actor", space)
    candidate = member_account("picker-member", space)
    revoked = member_account("picker-revoked", space)
    revoked.makerspace_memberships.update(status="revoked")
    outsider = member_account("picker-outsider", foreign)
    target = machine(space)
    url = f"/api/v1/admin/machines/{target.pk}/usage-candidates"
    response = authenticated_client(actor).get(url)
    assert response.status_code == 200
    ids = {row["user_id"] for row in response.data["results"]}
    assert candidate.pk in ids and revoked.pk not in ids and outsider.pk not in ids
    assert actor.pk not in ids  # The staff picker is a separate account, never a usage member.
    assert authenticated_client(outsider).get(url).status_code in (403, 404)


def test_service_module_purge_removes_its_cost_records_but_keeps_manual_pool_costs():
    from apps.makerspaces.module_purge_collectors_machine_service import machine_service_delete
    space = make_space("cost-module-purge")
    actor = make_member("cost-module-purge-manager", space)
    target = machine(space)
    pool = create_pool(space, actor, material="Material", initial_grams=100,
                       unit_cost=Decimal(1), cost_currency="USD", cost_unit="grams")
    usage = log_typed_manual_usage(target, actor, duration_minutes=1, outcome="success", percent_complete=100,
                                   grams=1, pool=pool)
    row = request(space, actor=actor, target=target)
    accept(row, actor)
    start(row, actor, role_scope.EXEMPT, machine_id=target.pk, consumable_pool_id=pool.pk, planned_grams=Decimal(2))
    complete(row, actor, actual_minutes=1, consumptions=[])
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")
        counts = machine_service_delete(space, cursor)
    assert counts["consumable_cost_records"] == 1
    assert ConsumableCostRecord.objects.get().source_kind == "manual_adjustment"
    assert MachineUsageEntry.objects.filter(pk=usage.pk).exists()
