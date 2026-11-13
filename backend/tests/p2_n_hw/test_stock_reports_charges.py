from decimal import Decimal

import pytest
from django.utils import timezone

from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_resolution import resolve
from apps.integrations.notification_sources import source_eligible
from apps.hardware_requests.notifications_p2_requests import notify_charge
from apps.hardware_requests.notifications_p2_reports import notify_report
from apps.hardware_requests.models import PublicToolLoan, PublicProblemReport
from apps.machines.notifications_p2_stock import notify as notify_stock
from apps.procurement.models import ToBuyItem
from apps.payments.models import Payment
from tests.p2_n_hw.test_hardware import loan

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("event,subject_type", [
    ("deposit_raised", "loan_deposit"), ("late_fee_raised", "loan_late_fee"),
])
def test_loan_charge_is_staff_summary_and_deduplicated(equipment, event, subject_type):
    row = loan(equipment)
    payment = Payment.objects.create(makerspace=equipment.space, subject_type=subject_type,
        subject_id=row.pk, member=equipment.owner, created_by=equipment.manager,
        amount=Decimal("12.00"), currency="inr", provider="unclaimed")
    assert notify_charge(row, event, payment).scheduled
    # The ledger owns the owner's charge notice; the domain adds a staff summary only.
    assert not NotificationEnvelope.objects.filter(source_kind="hardware.charge", audience="requester").exists()
    staff = NotificationEnvelope.objects.get(source_kind="hardware.charge", audience="staff", event=event)
    assert staff.recipient_id == equipment.manager.pk and "12.00" not in equipment.render(staff)["text"]
    notify_charge(row, event, payment)
    assert NotificationEnvelope.objects.filter(source_kind="hardware.charge").count() == 1


def test_problem_report_coverage_has_no_requester_body(equipment):
    row = loan(equipment, "returned")
    tool_loan = PublicToolLoan.objects.create(makerspace=equipment.space, request=row,
        requester=equipment.owner, target_type="product", target_id=1, target_label="Drill", status="returned")
    report = PublicProblemReport.objects.create(makerspace=equipment.space, request=row,
        loan=tool_loan, requester=equipment.owner, note="Private borrower account of damage")
    assert notify_report(report).scheduled
    envelope = NotificationEnvelope.objects.get(source_kind="hardware.problem_report")
    assert envelope.audience == "staff" and envelope.recipient_id == equipment.manager.pk
    assert report.note not in equipment.render(envelope)["text"]
    assert equipment.owner.email not in equipment.render(envelope)["text"]
    report.resolved_at = timezone.now()
    report.save(update_fields=["resolved_at"])
    assert not source_eligible(envelope)


@pytest.mark.parametrize("event,status", [("low_stock", "requested"), ("procurement_received", "received")])
def test_consumable_and_procurement_coverage(equipment, event, status):
    item = ToBuyItem.objects.create(makerspace=equipment.space, name="Filament", kind="printing",
        status=status, created_by=equipment.manager)
    assert notify_stock(item, event).scheduled
    envelope = NotificationEnvelope.objects.get(source_kind="machines.procurement")
    assert envelope.audience == "staff" and envelope.recipient_id == equipment.manager.pk
    assert {target.channel for target in resolve(envelope)} == {"telegram"}
    assert source_eligible(envelope)
