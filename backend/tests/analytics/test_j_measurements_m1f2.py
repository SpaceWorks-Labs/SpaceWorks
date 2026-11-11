from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.makerspaces.models import MakerspaceMembership
from apps.machines.models import Machine, MachineConsumableAdjustment, MachineConsumablePool, MachineServiceRequest, MachineType, MachineUsageEntry, ServiceBucket
from apps.machines.models_tracking import ConsumableCostRecord
from apps.operations import reports
from apps.operations.platform_scope import _platform_context_for_view
from apps.payments.models import Payment, Refund
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.return_helpers import make_member, make_space, make_user

pytestmark = pytest.mark.django_db


def machine(space, name):
    kind = MachineType.objects.create(makerspace=space, name=name, slug=name)
    return Machine.objects.create(makerspace=space, machine_type=kind, name=name)


def platform_actor():
    return make_user("j-measure-admin", role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE)


def usage(actor):
    return reports.report_data("platform-usage", platform_context=_platform_context_for_view(SimpleNamespace(user=actor)), limit=500)


def test_platform_machine_hours_are_per_machine_and_manual_and_service_stay_separate():
    # Platform accounts hold no makerspace membership (account kinds), so they
    # cannot carry a local machine-type scope; their machine reach is unscoped.
    space = make_space("j-machine-scope")
    space.enabled_modules = list(set(space.enabled_modules) | {"machines", "machine_service"})
    space.save(update_fields=["enabled_modules"])
    actor = platform_actor()
    assert not MakerspaceMembership.objects.filter(user=actor).exists()
    linked, excluded = machine(space, "linked"), machine(space, "excluded")
    requester = make_member("j-machine-requester", space)
    for row, hours in ((linked, "2"), (excluded, "99")):
        MachineUsageEntry.objects.create(machine=row, hours=hours, started_at=timezone.now())
        bucket = ServiceBucket.objects.create(machine=row, name="Main")
        MachineServiceRequest.objects.create(makerspace=space, bucket=bucket, assigned_machine=row, requester=requester,
                                              title="Private", status="completed", completed_at=timezone.now(), actual_minutes=180)
    data = usage(actor)
    machine_rows = [r for r in data["typed_rows"] if r["entity_kind"] == "machine"]
    assert {(r["entity_id"], r["metric"]): Decimal(str(r["value"])) for r in machine_rows} == {
        (str(linked.pk), "manual_machine_hours"): Decimal(2), (str(linked.pk), "service_machine_hours"): Decimal(3),
        (str(excluded.pk), "manual_machine_hours"): Decimal(99), (str(excluded.pk), "service_machine_hours"): Decimal(3),
    }
    assert_report_disclosure_safe(data)


def test_finalized_service_quantity_is_counted_even_without_reconcile_and_reserve_is_excluded():
    space = make_space("j-consumption")
    space.enabled_modules = list(set(space.enabled_modules) | {"machines", "machine_service"})
    space.save(update_fields=["enabled_modules"])
    actor = platform_actor()
    row = machine(space, "meter")
    bucket = ServiceBucket.objects.create(machine=row, name="Main")
    pool = MachineConsumablePool.objects.create(makerspace=space, machine=row, material="material",
                                               initial_grams=100, remaining_grams=75, unit="grams")
    service = MachineServiceRequest.objects.create(makerspace=space, bucket=bucket, assigned_machine=row, requester=actor,
                                                    title="Private", status="completed", completed_at=timezone.now(),
                                                    run_consumable_pool=pool, actual_consumed_quantity=25, actual_consumed_grams=25)
    MachineConsumableAdjustment.objects.create(makerspace=space, consumable_pool=pool, kind="reserve", quantity_delta=-25,
                                               service_request=service, consumed_quantity=-25)
    ConsumableCostRecord.objects.create(makerspace=space, source_kind="pooled_service", source_id=service.pk, quantity=25,
                                       measurement_unit="grams", unit_price_minor_per_measurement_unit=10, cost_total_minor=250, currency="usd")
    data = usage(actor)
    consumption = [r for r in data["typed_rows"] if r["metric"] == "consumables"]
    assert len(consumption) == 1 and Decimal(consumption[0]["value"]) == 25
    assert consumption[0]["unit"] == "grams"
    costs = [r for r in data["typed_rows"] if r["metric"] == "consumable_cost"]
    assert len(costs) == 1 and costs[0]["value"] == 250 and costs[0]["currency"] == "usd"
    assert_report_disclosure_safe(data)


def test_connect_attributed_ledger_facts_keep_currencies_and_do_not_invent_failure_attempts():
    space = make_space("j-connect")
    actor = platform_actor()
    member = make_member("j-connect-member", space)
    membership = MakerspaceMembership.objects.get(user=member, makerspace=space)
    for currency, amount in (("usd", "10.00"), ("eur", "20.00")):
        # Membership type has a unique subject, so use a distinct member per charge.
        if currency == "eur":
            member = make_member("j-connect-eur-member", space)
            membership = MakerspaceMembership.objects.get(user=member, makerspace=space)
        payment = Payment.objects.create(makerspace=space, subject_type="makerspace_membership", subject_id=membership.pk,
                                          member=member, created_by=actor, provider="stripe", stripe_provider="connect",
                                          stripe_connected_account_id="acct_private", status="paid_online", amount=amount, currency=currency)
        Refund.objects.create(payment=payment, amount=Decimal(amount) / 2, currency=currency, provider="stripe",
                              status="succeeded", settled_at=timezone.now(), created_by=actor)
    data = reports.report_data("platform-services", platform_context=_platform_context_for_view(SimpleNamespace(user=actor)), limit=500)
    rows = [r for r in data["typed_rows"] if r["service"] == "connect"]
    assert {r["status"] for r in rows} == {"charge", "online_settlement", "refund"}
    assert {r["currency"] for r in rows} == {"usd", "eur"}
    assert all(r["count"] == 1 for r in rows)
    assert_report_disclosure_safe(data)
