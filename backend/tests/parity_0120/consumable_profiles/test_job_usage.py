"""A job's profile consumables: estimates, actuals, required gating, stock draws and charges (decision 341)."""
import pytest
from django.urls import reverse
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.machines import consumable_usage as usage, role_scope, service_workflow_review as review
from apps.machines.models import MachineConsumableAdjustment
from apps.machines.models_consumable_profiles import ServiceRequestConsumableUsage as Usage
from apps.machines.service_errors import ServiceConsumptionInvalid
from apps.machines.service_workflow import complete, fail, start
from apps.payments.models import Payment
from tests.machines.eta_helpers import job, owner
from tests.machines.test_job_flow import priced
from tests.return_helpers import make_product

from .helpers import D, client, define, pool, running_job, world

pytestmark = pytest.mark.django_db


def test_member_estimates_follow_the_profile_units_and_required_flags():
    w = world("use-est")
    define(w, "vinyl", unit="m", estimate_by="member", required=True, attributes={"colour": ["Red", "Blue"]})
    define(w, "sheet", unit="sheet", estimate_by="staff")
    row = job(w)
    with pytest.raises(ValidationError):
        usage.record_estimates(row, row.member, [], source="member")  # the required one is missing
    with pytest.raises(ValidationError):
        usage.record_estimates(row, row.member, [{"key": "sheet", "quantity": 1}], source="member")  # staff estimate it
    with pytest.raises(ValidationError):
        usage.record_estimates(row, row.member, [{"key": "vinyl", "quantity": 1, "attributes": {"colour": "Green"}}],
                               source="member")
    with pytest.raises(ValidationError):
        usage.record_estimates(row, row.member, [{"key": "laser", "quantity": 1}], source="member")
    rows = usage.record_estimates(row, row.member, [{"key": "vinyl", "quantity": "1.5", "attributes": {"colour": "red"}}],
                                  source="member")
    assert rows[0].quantity == D("1.5") and rows[0].source == "member" and rows[0].unit == "m"


@pytest.mark.parametrize("quantity", [0, -1, "abc", True, "0.0001"])
def test_quantities_must_be_positive_numbers(quantity):
    w = world("use-qty")
    define(w, "filament", unit="g")
    row, _ = running_job(w)
    with pytest.raises(ValidationError):
        usage.record_actuals(row, w.staff, [{"key": "filament", "quantity": quantity}], source="staff")


def test_whole_units_refuse_fractions():
    w = world("use-whole")
    define(w, "sheet")
    row, _ = running_job(w)
    with pytest.raises(ValidationError):
        usage.record_actuals(row, w.staff, [{"key": "sheet", "quantity": "1.5"}], source="staff")


def test_a_required_consumable_gates_completion_until_recorded():
    w = world("use-req")
    define(w, "sheet", required=True)
    row, _ = running_job(w)
    with pytest.raises(ServiceConsumptionInvalid):
        complete(row, w.staff, actual_minutes=5, consumptions=[])
    done = complete(row, w.staff, actual_minutes=5, consumptions=[],
                    profile_consumptions=[{"key": "sheet", "quantity": 2}])
    assert done.status == "completed" and Usage.objects.get(service_request=done, phase="actual").quantity == 2


def test_a_failed_job_does_not_need_its_required_consumables():
    w = world("use-fail")
    define(w, "sheet", required=True)
    row, _ = running_job(w)
    assert fail(row, w.staff, reason="Warped", percent_complete=40, actual_minutes=3, consumptions=[]).status == "failed"


def test_an_actual_is_recorded_once_and_a_replay_is_a_no_op():
    w = world("use-once")
    define(w, "sheet")
    row, _ = running_job(w)
    assert len(usage.record_actuals(row, w.staff, [{"key": "sheet", "quantity": 1}], source="staff")) == 1
    assert usage.record_actuals(row, w.staff, [{"key": "sheet", "quantity": 1}], source="staff") == []
    with pytest.raises(ValidationError):
        usage.record_actuals(row, w.staff, [{"key": "sheet", "quantity": 3}], source="staff")
    assert AuditLog.objects.filter(action="machine_service.consumables_recorded", makerspace=w.space).count() == 1


def test_a_linked_pool_is_drawn_through_the_pool_ledger_in_pool_units():
    w = world("use-pool")
    grams = pool(w, unit="grams", initial="2000", material="PLA")
    define(w, "filament", unit="kg", consumable_pool=grams)
    row, _ = running_job(w)
    usage.record_actuals(row, w.staff, [{"key": "filament", "quantity": "0.25"}], source="staff")
    grams.refresh_from_db()
    assert grams.remaining_grams == D("1750")
    adjustment = MachineConsumableAdjustment.objects.get(consumable_pool=grams)
    assert adjustment.kind == "manual" and adjustment.quantity_delta == D("-250")
    assert adjustment.service_request_id == row.pk


def test_a_short_pool_is_drawn_to_zero_and_the_shortfall_audited():
    w = world("use-short")
    sheets = pool(w, unit="count", initial="1")
    define(w, "sheet", consumable_pool=sheets)
    row, _ = running_job(w)
    usage.record_actuals(row, w.staff, [{"key": "sheet", "quantity": 3}], source="staff")
    sheets.refresh_from_db()
    assert sheets.remaining_grams == 0
    assert AuditLog.objects.filter(action="machine_service.consumable_stock_short", makerspace=w.space).exists()


def test_low_stock_runs_through_the_existing_pool_alert(monkeypatch):
    calls = []
    monkeypatch.setattr("apps.machines.low_stock.maybe_flag_low_stock", lambda actor, pool_row: calls.append(pool_row.pk))
    w = world("use-low")
    sheets = pool(w, unit="count", initial="5", low="4")
    define(w, "sheet", consumable_pool=sheets)
    row, _ = running_job(w)
    usage.record_actuals(row, w.staff, [{"key": "sheet", "quantity": 2}], source="staff")
    assert calls == [sheets.pk]


def test_the_pool_the_job_reserved_is_not_drawn_twice():
    w = world("use-reserved")
    sheets = pool(w, unit="count", initial="5")
    define(w, "sheet", consumable_pool=sheets)
    row, _ = running_job(w)
    type(row).objects.filter(pk=row.pk).update(run_consumable_pool=sheets)
    row.refresh_from_db()
    usage.record_actuals(row, w.staff, [{"key": "sheet", "quantity": 2}], source="staff")
    sheets.refresh_from_db()
    assert sheets.remaining_grams == D("5")


def test_a_linked_inventory_item_is_consumed_through_inventory_availability():
    w = world("use-item")
    boards = make_product(w.space, "Copper board", total_quantity=5, available_quantity=5)
    define(w, "board", unit="piece", product=boards)
    row, _ = running_job(w)
    usage.record_actuals(row, w.staff, [{"key": "board", "quantity": 2}], source="staff")
    boards.refresh_from_db()
    assert boards.available_quantity == 3


def test_recorders_follow_the_profile_and_members_report_only_their_own_running_job():
    w = world("use-who")
    define(w, "sheet", record_by=["staff"])
    define(w, "tape", unit="m", record_by=["staff", "member"])
    row, member = running_job(w)
    with pytest.raises(ValidationError):
        usage.record_actuals(row, member, [{"key": "sheet", "quantity": 1}], source="member")
    with pytest.raises(ValidationError):
        usage.record_actuals(row, None, [{"key": "tape", "quantity": 1}], source="adapter")
    url = reverse("member-machine-job-consumables", kwargs={"pk": row.pk})
    stranger = client(owner("use-who-stranger")).post(url, [{"key": "tape", "quantity": 1}], format="json")
    assert stranger.status_code in (403, 404)
    response = client(member).post(url, [{"key": "tape", "quantity": "0.5"}], format="json")
    assert response.status_code == 200 and response.data[0]["source"] == "member"


def test_staff_endpoint_reads_and_records_inside_the_machine_scope():
    w = world("use-api")
    define(w, "sheet", required=True)
    row, _ = running_job(w)
    url = reverse("admin-machine-job-consumables", kwargs={"makerspace_id": w.space.pk, "pk": row.pk})
    assert client(w.staff).get(url).data["missing_required"] == ["sheet"]
    body = {"phase": "actual", "entries": [{"key": "sheet", "quantity": 1}]}
    response = client(w.staff).post(url, body, format="json")
    assert response.status_code == 200 and response.data["missing_required"] == []
    assert client(owner("use-api-member")).get(url).status_code in (403, 404)


def test_quote_prices_estimates_and_the_charge_prices_actuals():
    w = priced(world("use-money"), rate="1.00", flat="0.00")
    define(w, "sheet", unit_price=D("4.00"), estimate_by="staff")
    member = owner("use-money-m")
    row = review.send_quote(job(w, member=member), w.staff, estimated_minutes=10,
                            consumable_estimates=[{"key": "sheet", "quantity": 2}])
    lines = {line["component"]: line for line in row.quote_snapshot["lines"]}
    assert D(lines["consumable"]["net"]) == D("8.00") and lines["consumable"]["detail"]["unit"] == "sheet"
    quoted = D(row.quote_snapshot["total"])
    row = review.approve_quote(row, member, digest=row.quote_digest)
    start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    complete(row, w.staff, actual_minutes=10, consumptions=[], profile_consumptions=[{"key": "sheet", "quantity": 1}])
    payment = Payment.objects.get(subject_type="machine_service_request", subject_id=row.pk)
    assert payment.amount == quoted - D("4.00")  # same minutes; one sheet used instead of two


def test_failed_material_only_keeps_material_lines_and_drops_the_rest():
    from apps.payments.pricing.build_machines import consumable_lines
    from apps.payments.pricing.resolver import rate_card
    w = world("use-fail-lines")
    card = rate_card(w.space, "machines")
    items = [{"definition_id": 1, "key": "sheet", "name": "Sheet", "kind": "material", "unit": "sheet",
              "quantity": D(1), "unit_price": D("3")},
             {"definition_id": 2, "key": "bit", "name": "Bit", "kind": "tool_wear", "unit": "use",
              "quantity": D(1), "unit_price": D("5")}]
    assert [line.label for line in consumable_lines(card, items, full=False)] == ["Sheet"]
    assert [line.gross for line in consumable_lines(card, items)] == [D("3"), D("5")]
