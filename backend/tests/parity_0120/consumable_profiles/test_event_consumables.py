"""Event machine use counts profile actuals too, without restating the pool ledger (decisions 341/342)."""
import pytest

from apps.events.machine_use_summary import rows_for
from apps.events.models_machine_use import MachineEventLink
from apps.machines import consumable_usage as usage
from tests.events.checkin_helpers import make_event

from .helpers import D, define, pool, report_dicts, running_job, world

pytestmark = pytest.mark.django_db


def linked_job(w, event):
    row, _ = running_job(w)
    MachineEventLink.objects.create(makerspace=w.space, event=event, machine_type=w.kind, service_request=row,
                                    source=MachineEventLink.Source.MANAGER)
    return row


def test_profile_actuals_appear_on_the_event_and_in_the_report():
    w = world("evt-cons")
    w.space.enabled_modules = sorted({*w.space.enabled_modules, "events", "reports"})
    w.space.save(update_fields=["enabled_modules"])
    event = make_event(w.space)
    define(w, "sheet", unit_price=D("2.00"))
    define(w, "bit", kind="tool_wear", unit="use")
    row = linked_job(w, event)
    usage.record_actuals(row, w.staff, [{"key": "sheet", "quantity": 2}, {"key": "bit", "quantity": 1}], source="staff")
    [line] = rows_for(event)
    assert sorted((item["label"], item["unit"], item["quantity"]) for item in line["consumables"]) == [
        ("Bit", "use", "1.000"), ("Sheet", "sheet", "2.000")]
    [summary] = report_dicts("machine-use-by-event", w.space.pk, actor=w.staff)
    assert summary["consumable_entries"] == 2


def test_an_actual_restating_the_reserved_pool_is_not_counted_twice():
    w = world("evt-dup")
    event = make_event(w.space)
    reserved = pool(w, unit="grams", initial="1000", material="PLA")
    define(w, "filament", unit="g", consumable_pool=reserved)
    define(w, "material", unit="g")  # the upgrade-seeded primary row: no stock link
    define(w, "support", unit="g")
    row = linked_job(w, event)
    type(row).objects.filter(pk=row.pk).update(run_consumable_pool=reserved)
    row.refresh_from_db()
    usage.record_actuals(row, w.staff, [{"key": "filament", "quantity": 10}, {"key": "material", "quantity": 10},
                                        {"key": "support", "quantity": 3}], source="staff")
    assert usage.event_consumables([row.pk]) == {row.pk: [{"label": "Support", "unit": "g", "quantity": "3.000"}]}
