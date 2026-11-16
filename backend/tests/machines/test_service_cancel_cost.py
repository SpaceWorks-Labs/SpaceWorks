"""Decision 58: cancelling a RUNNING job records its consumable cost, never a charge."""

from decimal import Decimal

import pytest

from apps.machines import role_scope, service_consumable_pools as pools
from rest_framework.test import APIClient

from apps.machines.models import MachineConsumablePool, MachineServiceRequest
from apps.machines.models_tracking import ConsumableCostRecord
from apps.machines.service_workflow import cancel, start
from apps.payments.models import Payment
from tests.machines.eta_helpers import approved, owner, world

pytestmark = pytest.mark.django_db


def _priced_pool(w):
    pool = pools.create_pool(w.space, w.staff, material="Sheet", quantity="100", machine_type=w.kind, unit="grams")
    MachineConsumablePool.objects.filter(pk=pool.pk).update(
        unit_cost=Decimal("0.05"), cost_currency="USD", cost_unit="grams")
    pool.refresh_from_db()
    return pool


@pytest.mark.parametrize("by_owner", [False])  # #141/#142: only staff cancel a running job
def test_cancelling_a_running_job_records_its_cost_without_a_charge(by_owner):
    w = world(f"cancel-cost-{int(by_owner)}")
    member = owner(f"cancel-cost-owner-{int(by_owner)}")
    row = approved(w, 30, created=-5, member=member)
    start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    pool = _priced_pool(w)
    pools.reserve_for_request(row, w.staff, pool=pool, planned_grams="20", machine=w.machines[0])

    cancel(row, member if by_owner else w.staff, reason="Stopped early", by_owner=by_owner)

    row.refresh_from_db()
    record = ConsumableCostRecord.objects.get(makerspace=w.space, source_kind="pooled_service", source_id=row.pk)
    assert record.quantity == row.actual_consumed_quantity
    assert record.currency == "USD" and record.measurement_unit == "grams"
    assert not Payment.objects.filter(subject_type="machine_service_request", subject_id=row.pk).exists()
    # A repeated cancel returns the terminal row and never records a second cost.
    cancel(row, member if by_owner else w.staff, by_owner=by_owner)
    assert ConsumableCostRecord.objects.filter(source_kind="pooled_service", source_id=row.pk).count() == 1


def test_cancelling_a_waiting_job_records_no_cost():
    w = world("cancel-cost-waiting")
    member = owner("cancel-cost-waiting-owner")
    row = approved(w, 30, created=-5, member=member)
    pool = _priced_pool(w)
    pools.reserve_for_request(row, w.staff, pool=pool, planned_grams="20", machine=w.machines[0])

    cancel(row, member, by_owner=True)

    assert not ConsumableCostRecord.objects.filter(source_kind="pooled_service", source_id=row.pk).exists()


# Decision 61a: a running cancel may confirm the material used so far.

def _running_with_hold(slug, *, member=None):
    w = world(slug)
    row = approved(w, 30, created=-5, member=member)
    start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    pool = _priced_pool(w)
    pools.reserve_for_request(row, w.staff, pool=pool, planned_grams="20", machine=w.machines[0])
    pool.refresh_from_db()
    return w, row, pool


def test_confirmed_material_stays_taken_and_is_costed_without_a_charge():
    w, row, pool = _running_with_hold("cancel-used")
    before = pool.remaining_grams
    cancel(row, w.staff, reason="Nozzle jam", consumed_quantity=Decimal("7.5"))
    row.refresh_from_db()
    pool.refresh_from_db()
    assert row.status == "cancelled" and row.actual_consumed_quantity == Decimal("7.50")
    assert row.reserved_quantity in (None, Decimal("0")) and row.reserved_grams == Decimal("0")
    assert pool.remaining_grams == before + Decimal("12.5")  # only the unused part returns
    record = ConsumableCostRecord.objects.get(source_kind="pooled_service", source_id=row.pk)
    assert record.quantity == Decimal("7.50") and record.cost_total_minor > 0
    assert not Payment.objects.filter(subject_type="machine_service_request", subject_id=row.pk).exists()


@pytest.mark.parametrize("amount", [None, Decimal("0")])
def test_empty_or_zero_keeps_the_zero_consumption_release(amount):
    w, row, pool = _running_with_hold(f"cancel-zero-{amount}")
    cancel(row, w.staff, consumed_quantity=amount)
    row.refresh_from_db()
    pool.refresh_from_db()
    assert row.actual_consumed_quantity in (None, Decimal("0"))
    assert pool.remaining_grams == pool.initial_grams


def test_more_than_the_hold_or_a_waiting_job_is_refused():
    from rest_framework.exceptions import ValidationError
    w, row, pool = _running_with_hold("cancel-too-much")
    with pytest.raises(ValidationError):
        cancel(row, w.staff, consumed_quantity=Decimal("20.01"))
    row.refresh_from_db()
    assert row.status == "in_progress"
    waiting = approved(w, 30, created=-4)
    with pytest.raises(ValidationError):
        cancel(waiting, w.staff, consumed_quantity=Decimal("1"))
    waiting.refresh_from_db()
    assert waiting.status == "accepted"


def test_both_cancel_routes_accept_the_confirmed_amount():
    from tests.return_helpers import authenticated_client
    w, row, _pool = _running_with_hold("cancel-api-staff")
    response = authenticated_client(w.staff).post(f"/api/v1/admin/machine-service/requests/{row.pk}/cancel",
                                                  {"consumed_quantity": "5"}, format="json")
    assert response.status_code == 200, response.content
    assert MachineServiceRequest.objects.get(pk=row.pk).actual_consumed_quantity == Decimal("5.00")
    over_world, over_row, _ = _running_with_hold("cancel-api-over")
    too_much = authenticated_client(over_world.staff).post(
        f"/api/v1/admin/machine-service/requests/{over_row.pk}/cancel", {"consumed_quantity": "99"}, format="json")
    assert too_much.status_code == 400 and "consumed_quantity" in too_much.content.decode()
    member = owner("cancel-api-owner")
    w2, owned, _ = _running_with_hold("cancel-api-member", member=member)
    client = APIClient()
    client.force_authenticate(member)
    owned_response = client.post(f"/api/v1/member/machine-service/requests/{owned.pk}/cancel",
                                 {"consumed_quantity": "2"}, format="json")
    # #141: a member cancels only before In progress; a running job is the staff's to stop.
    assert owned_response.status_code == 403, owned_response.content
    assert MachineServiceRequest.objects.get(pk=owned.pk).status == "in_progress"
