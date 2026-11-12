"""Every subject converges on one debt hook; bill failures roll back only a savepoint."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.hardware_requests.models import HardwareRequest
from apps.makerspaces.models import MembershipRequest, MembershipTerm
from apps.payments.bill_sweeper import issue_missing_bills
from apps.payments.models import Payment, MakerspaceBillingSettings
from apps.payments.services import create_payment
from tests.makerspaces.test_membership_plans import plan
from tests.payments.test_machine_payments import service_request
from tests.payments.test_new_subjects import subjects
from tests.return_helpers import make_space, make_member

pytestmark = pytest.mark.django_db


def _subject_id(rows, subject_type):
    """Subjects added after release 1 (events, shop, donations, day passes) raise their charge by
    id only; the bill hook needs the canonical seam, not the domain row, so a bare id stands in."""
    row = rows.get(subject_type)
    return row.pk if row is not None else 987654


def charge_inputs(subject_type, slug="r1-hook"):
    space = make_space(slug)
    actor = make_member(slug + "-staff", space)
    payer = make_member(slug + "-payer", space, membership_role="custom", role="requester")
    rows = subjects(space, payer)
    rows["machine_service_request"] = service_request(space, payer)
    loan = HardwareRequest.objects.create(makerspace=space, requester=payer, requester_username=payer.username)
    rows.update(loan_deposit=loan, loan_late_fee=loan, loan_rental=loan)
    from apps.hardware_requests.models import RequesterAccountability
    for kind, issue in (("loan_damage", "damaged"), ("loan_lost", "missing")):
        rows[kind] = RequesterAccountability.objects.create(requester=payer, request=loan, makerspace=space,
                                                            issue_type=issue, quantity=1, created_by=actor)
    rows["membership_request"] = MembershipRequest.objects.create(
        makerspace=space, user=payer, kind="request", state="awaiting_payment")
    rows["membership_term"] = MembershipTerm.objects.create(
        membership=rows["makerspace_membership"], plan=plan(space), starts_at=timezone.now(),
        ends_at=timezone.now() + timedelta(days=30))
    return dict(makerspace=space, member=payer, created_by=actor, subject_type=subject_type,
                subject_id=_subject_id(rows, subject_type), amount=Decimal("10.00"), currency="usd")


@pytest.mark.parametrize("subject_type", Payment.SubjectType.values)
def test_all_eight_subjects_issue_bill_at_the_canonical_charge_boundary(subject_type):
    values = charge_inputs(subject_type)
    payment = create_payment(**values)
    bill = payment.documents.get(kind="bill")
    assert bill.amount == payment.amount and bill.payer_label == values["member"].username
    assert AuditLog.objects.filter(makerspace=values["makerspace"], action="payment.document_issued",
                                   meta__kind="bill").count() == 1


def test_database_failure_in_optional_bill_does_not_poison_mandatory_outer_transaction(monkeypatch):
    values = charge_inputs("booking", "r1-savepoint")
    from apps.payments.documents import issue_bill as real_issue_bill
    def break_bill(payment, **kwargs):
        real_issue_bill(payment, **kwargs)
        # A real failed SQL statement after document writes, rather than a harmless Python exception.
        with transaction.get_connection().cursor() as cursor:
            cursor.execute("SELECT 1 / 0")
    monkeypatch.setattr("apps.payments.documents.issue_bill", break_bill)
    with transaction.atomic():
        payment = create_payment(**values)
        assert Payment.objects.filter(pk=payment.pk).exists()  # transaction still usable
        assert AuditLog.objects.filter(action="payment.created", target_id=str(payment.pk)).exists()
    assert not payment.documents.exists()
    assert not MakerspaceBillingSettings.objects.filter(makerspace=payment.makerspace).exists()
    assert not AuditLog.objects.filter(makerspace=payment.makerspace, action="payment.document_issued").exists()


def test_sweeper_recovers_a_failed_bill_once_and_command_uses_the_same_service(monkeypatch):
    from django.core.management import call_command
    values = charge_inputs("membership_term", "r1-recover")
    with patch("apps.payments.documents.issue_bill", side_effect=RuntimeError("temporary failure")):
        payment = create_payment(**values)
    first = issue_missing_bills(makerspace_id=payment.makerspace_id)
    assert first["issued"] == 1 and first["failed"] == 0
    assert issue_missing_bills(makerspace_id=payment.makerspace_id)["issued"] == 0
    call_command("issue_missing_bills", makerspace_id=payment.makerspace_id)
    assert payment.documents.filter(kind="bill").count() == 1


def test_sweeper_does_not_issue_into_a_frozen_tenant():
    values = charge_inputs("loan_deposit", "r1-frozen")
    with patch("apps.payments.documents.issue_bill", return_value=None):
        payment = create_payment(**values)
    # Exercise the real boundary without fabricating the gate's custody constraints.
    from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
    with patch("apps.tenant_migration.gate_runtime.assert_write_allowed",
               side_effect=SourceMigrationGateClosed("Frozen", purpose="tenant_exit")):
        counts = issue_missing_bills(makerspace_id=payment.makerspace_id)
    assert counts["skipped"] == 1 and counts["issued"] == 0
    assert not payment.documents.exists()


def test_receipt_creation_remains_distinct_after_a_bill_and_no_rail_is_needed():
    from apps.payments.reconciliation import mark_offline
    from tests.return_helpers import settlement_details
    values = charge_inputs("membership_request", "r1-offline-bill")
    values["makerspace"].enabled_modules = []
    values["makerspace"].save(update_fields=["enabled_modules"])
    payment = create_payment(**values)
    assert payment.provider == "unclaimed"
    mark_offline(payment, values["created_by"], settlement_details())
    assert set(payment.documents.values_list("kind", flat=True)) == {"receipt", "bill"}
