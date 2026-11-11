"""#163A machine quotes and #171 (2)/(3): prepaid jobs get staff-approved refund cases, never money."""

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.machines import role_scope, service_workflow_review as review
from apps.machines.models import MakerspaceMachineTypePolicy
from apps.machines.service_workflow import cancel, complete, fail, start
from apps.payments.models import Payment, Refund, RefundCase
from apps.payments.reconciliation import mark_offline
from tests.l24_local.helpers import FEATURE, client, opened_rows, preview, setup
from tests.machines.eta_helpers import job, owner, world
from tests.machines.test_job_flow import priced
from tests.return_helpers import settlement_details

pytestmark = pytest.mark.django_db
D = Decimal


def prepaid_world(slug, *, on=True):
    w = priced(world(slug), rate="2.00", flat="5.00")  # 2.00 a minute + 5.00 a job
    setup(w.space, on=on)
    MakerspaceMachineTypePolicy.objects.create(makerspace=w.space, machine_type=w.kind, payment_timing="prepay")
    return w


def paid_job(w, slug, *, minutes=20, settle=True):
    member = owner(slug)
    row = review.send_quote(job(w, member=member), w.staff, estimated_minutes=minutes)
    row = review.approve_quote(row, member, digest=row.quote_digest)
    payment = Payment.objects.get(subject_type="machine_service_request", subject_id=row.pk)
    if settle:
        mark_offline(payment, w.staff, settlement=settlement_details())
        row = review.promote_prepaid(row)
        payment.refresh_from_db()
    return row, payment, member


def type_url(w):
    return reverse("admin-machine-type-pricing-detail", kwargs={"makerspace_id": w.space.pk,
                                                                "machine_type_id": w.kind.pk})


def test_type_price_drop_previews_and_opens_a_case_for_a_paid_job_not_started():
    w = prepaid_world("l24-job-drop")
    row, payment, _ = paid_job(w, "l24-job-drop-m")
    quoted = D(row.quote_snapshot["total"])
    body = {"rate_per_unit": "1.50", "flat_fee": "5.00", "payment_enabled": True}
    report = preview(client(w.staff).put(type_url(w) + "?price_drop_preview=1", body, format="json"))
    assert [(item["item_type"], item["item_id"]) for item in report["items"]] == [("machine_job", row.pk)]
    assert D(report["items"][0]["before"]) == quoted
    assert D(report["items"][0]["difference"]) == quoted - D(report["items"][0]["after"]) > 0
    assert not RefundCase.objects.exists()
    assert client(w.staff).put(type_url(w), body, format="json").status_code == 200
    case = RefundCase.objects.get(payment=payment)
    assert case.reason_code == "price_drop" and case.status == "open"
    assert case.due_amount == D(report["items"][0]["difference"])
    assert opened_rows("machines") and not Refund.objects.exists()


def test_type_price_rise_and_a_started_job_open_nothing():
    w = prepaid_world("l24-job-rise")
    row, payment, _ = paid_job(w, "l24-job-rise-m")
    started, started_payment, _ = paid_job(w, "l24-job-rise-s")
    start(started, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    rise = {"rate_per_unit": "3.00", "flat_fee": "5.00", "payment_enabled": True}
    assert client(w.staff).put(type_url(w), rise, format="json").status_code == 200
    assert not RefundCase.objects.exists()
    drop = {"rate_per_unit": "1.00", "flat_fee": "5.00", "payment_enabled": True}
    client(w.staff).put(type_url(w), drop, format="json")
    assert RefundCase.objects.filter(payment=payment).exists()
    assert not RefundCase.objects.filter(payment=started_payment).exists()


def test_switch_off_opens_no_price_drop_case_and_hides_the_preview():
    w = prepaid_world("l24-job-off", on=False)
    _, payment, _ = paid_job(w, "l24-job-off-m")
    body = {"rate_per_unit": "1.00", "flat_fee": "5.00", "payment_enabled": True}
    assert client(w.staff).put(type_url(w) + "?price_drop_preview=1", body, format="json").status_code == 404
    assert client(w.staff).put(type_url(w), body, format="json").status_code == 200
    assert not RefundCase.objects.exists()


def test_member_cancelling_a_paid_prepaid_job_before_it_starts_opens_a_case():
    w = prepaid_world("l24-job-cancel", on=False)  # #171 is not behind the price-drop switch
    row, payment, member = paid_job(w, "l24-job-cancel-m")
    cancel(row, member, by_owner=True)
    case = RefundCase.objects.get(payment=payment)
    assert (case.reason_code, case.status, case.due_amount) == ("job_cancelled", "open", payment.amount)
    assert case.policy_snapshot["shares"][0]["source"] == "job_cancelled"
    assert not Refund.objects.exists()
    assert AuditLog.objects.filter(action="payment.refund_case_opened", meta__case_id=case.pk).exists()


def test_member_cancelling_an_unpaid_prepaid_job_voids_its_charge():
    w = prepaid_world("l24-job-unpaid")
    row, payment, member = paid_job(w, "l24-job-unpaid-m", settle=False)
    cancel(row, member, by_owner=True)
    payment.refresh_from_db()
    assert payment.status == "canceled" and not RefundCase.objects.exists()


def test_staff_cancelling_a_paid_prepaid_job_keeps_the_staff_cancelled_case():
    w = prepaid_world("l24-job-staff")
    row, payment, _ = paid_job(w, "l24-job-staff-m")
    cancel(row, w.staff, reason="Machine retired")
    case = RefundCase.objects.get(payment=payment)
    assert case.reason_code == "staff_cancelled" and case.due_amount == payment.amount


def test_actual_cost_below_the_quote_opens_a_difference_case():
    w = prepaid_world("l24-job-cheaper", on=False)
    row, payment, _ = paid_job(w, "l24-job-cheaper-m", minutes=20)  # quote 45.00
    start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    complete(row, w.staff, actual_minutes=5, consumptions=[])  # actual 15.00
    case = RefundCase.objects.get(payment=payment)
    assert case.reason_code == "quote_difference" and case.status == "open"
    assert case.due_amount == payment.amount - D("15.00")
    assert not Refund.objects.exists()


def test_actual_cost_at_or_above_the_quote_opens_nothing():
    w = prepaid_world("l24-job-same")
    row, payment, _ = paid_job(w, "l24-job-same-m", minutes=20)
    start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    complete(row, w.staff, actual_minutes=60, consumptions=[])
    assert not RefundCase.objects.exists()
    assert Payment.objects.filter(subject_type="machine_service_request").count() == 1


def test_member_fault_failure_offers_back_what_the_failure_charge_did_not_take():
    w = prepaid_world("l24-job-fail")
    row, payment, _ = paid_job(w, "l24-job-fail-m")
    start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    fail(row, w.staff, reason="Bad file", percent_complete=10, actual_minutes=2, consumptions=[],
         code="file_problem", fault="member")
    case = RefundCase.objects.get(payment=payment)  # failures are free by default: all of it
    assert case.reason_code == "quote_difference" and case.due_amount == payment.amount


def test_no_case_without_machine_charging():
    w = prepaid_world("l24-job-notrack")
    row, payment, member = paid_job(w, "l24-job-notrack-m")
    w.space.enabled_features = [key for key in w.space.enabled_features if key != "charges.machines"]
    w.space.save(update_fields=["enabled_features"])
    cancel(row, member, by_owner=True)
    assert not RefundCase.objects.exists()
    assert FEATURE in w.space.enabled_features


def test_machine_override_and_rate_card_saves_reach_prepaid_jobs():
    from apps.payments.models import PriceOverride
    w = prepaid_world("l24-job-card")
    row, payment, _ = paid_job(w, "l24-job-card-m", minutes=20)  # 45.00 on the type row
    url = (f"/api/v1/admin/makerspace/{w.space.pk}/pricing/overrides/{PriceOverride.TargetType.MACHINE}/"
           f"{w.machines[0].pk}")
    # The quote named no machine, so a machine's own price cannot touch it.
    report = preview(client(w.staff).put(url + "?price_drop_preview=1",
                                         {"component": "per_job", "mode": "free"}, format="json"))
    assert report["count"] == 0
    card = f"/api/v1/admin/makerspace/{w.space.pk}/pricing/machines"
    assert client(w.staff).put(card, {"mode": "paid"}, format="json").status_code == 200
    assert not RefundCase.objects.exists()  # the type row still prices the job: nothing cheaper
    assert opened_rows("machines") == []
    assert payment.refund_cases.count() == 0 and row.pk


def test_a_job_cancelled_case_is_decided_by_the_jobs_machine_manager():
    from apps.payments.services_refund_decisions import decline_case
    from tests.return_helpers import make_print_manager
    w = prepaid_world("l24-job-mm", on=False)
    row, payment, member = paid_job(w, "l24-job-mm-m")
    cancel(row, member, by_owner=True)
    case = RefundCase.objects.get(payment=payment)
    manager = make_print_manager("l24-job-mm-manager", w.space)
    assert decline_case(case, actor=manager, note="Material already cut").status == "declined"
    assert not Refund.objects.exists()
