"""Bill issuance, append-only SQL custody, reconstruction and independent numbering."""

from copy import copy
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.payments.document_import import document_import_rows, GUC
from apps.payments.documents import issue_bill
from apps.payments.models import MakerspaceBillingSettings, Payment, PaymentDocument
from apps.payments.reconciliation import mark_offline
from apps.tenant_migration.raw_repository import RawImportRepository
from tests.payments.test_refunds import paid_deposit
from tests.return_helpers import make_space, make_member, settlement_details

pytestmark = pytest.mark.django_db


def pending(slug="r1-bill"):
    space = make_space(slug)
    actor = make_member(slug + "-staff", space)
    return space, actor, paid_deposit(space, actor, status="pending")


def bill_draft(payment, pk=9876501):
    return PaymentDocument(id=pk, makerspace=payment.makerspace, payment=payment,
        sequence=1, number=f"IMPORTED-{pk}", kind="bill", issuer={"name": "Historical issuer"},
        payer_label=payment.member.username, payer_type="member",
        lines=[{"label": "Charge", "quantity": "1", "unit_amount": str(payment.amount), "total": str(payment.amount)}],
        amount=payment.amount, currency=payment.currency, settlement_method="", money_at=timezone.now())


def test_idempotency_and_bill_receipt_sequences_are_independent():
    space, actor, payment = pending()
    bill = issue_bill(payment, actor=actor)
    assert (bill.number, bill.sequence) == ("BILL-000001", 1)
    assert issue_bill(payment).pk == bill.pk
    mark_offline(payment, actor, settlement_details())
    receipt = payment.documents.get(kind="receipt")
    assert receipt.sequence == 1 and receipt.number == "000001"
    assert issue_bill(payment).pk == bill.pk  # idempotent even after settlement
    policy = MakerspaceBillingSettings.objects.get(makerspace=space)
    assert policy.next_document_number == policy.next_bill_number == 2
    assert AuditLog.objects.filter(target_id=str(bill.pk), action="payment.document_issued").exists()


def test_prefix_edits_skip_existing_numbers_under_the_same_counter_lock():
    space, actor, payment = pending("r1-collision")
    policy = MakerspaceBillingSettings.objects.create(makerspace=space, number_prefix="BILL-", bill_prefix="INV-")
    mark_offline(payment, actor, settlement_details())
    policy.number_prefix, policy.bill_prefix = "REC-", "BILL-"
    policy.save(update_fields=["number_prefix", "bill_prefix"])
    another = paid_deposit(space, actor, status="pending", intent="pi_collision")
    bill = issue_bill(another)
    assert bill.number == "BILL-000002" and bill.sequence == 2
    policy.refresh_from_db()
    assert policy.next_bill_number == 3


def test_bill_is_append_only_and_one_per_payment_even_when_bypassing_model_save():
    _, _, payment = pending("r1-one-bill")
    bill = issue_bill(payment)
    duplicate = copy(bill)
    duplicate.pk, duplicate.number, duplicate.sequence = None, "DUPLICATE", 2
    with pytest.raises(DatabaseError), transaction.atomic():
        PaymentDocument.objects.bulk_create([duplicate])
    with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
        payment.documents.update(payer_label="changed")
    with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
        payment.documents.all().delete()


@pytest.mark.parametrize("status", ["paid_online", "paid_offline", "waived", "canceled"])
def test_normal_insert_refuses_historical_bill_but_raw_import_accepts_it(status):
    space, _, payment = pending("r1-import-" + status)
    Payment.objects.filter(pk=payment.pk).update(status=status)
    payment.refresh_from_db()
    draft = bill_draft(payment)
    with pytest.raises(ValidationError, match="pending"):
        draft.clean()
    with pytest.raises(DatabaseError, match="pending"), transaction.atomic():
        PaymentDocument.objects.bulk_create([draft])
    row = {field.column: getattr(draft, field.attname) for field in PaymentDocument._meta.local_concrete_fields}
    row["issued_at"] = timezone.now()
    with transaction.atomic():
        RawImportRepository().insert_rows(PaymentDocument, [row])
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting(%s, true)", [GUC])
            assert cursor.fetchone()[0] in (None, "")
    assert payment.documents.get(kind="bill").issuer["name"] == "Historical issuer"


def test_exact_id_import_exception_does_not_bypass_tenant_amount_currency_or_sources():
    space, _, payment = pending("r1-import-guards")
    Payment.objects.filter(pk=payment.pk).update(status="waived")
    foreign = make_space("r1-import-foreign")
    for changes in ({"makerspace": foreign}, {"amount": Decimal("9.00")}, {"currency": "eur"}):
        draft = bill_draft(payment)
        for key, value in changes.items():
            setattr(draft, key, value)
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            with document_import_rows(cursor, PaymentDocument, [draft.pk]):
                PaymentDocument.objects.bulk_create([draft])
    draft = bill_draft(payment)
    with pytest.raises(DatabaseError, match="pending"), transaction.atomic(), connection.cursor() as cursor:
        with document_import_rows(cursor, PaymentDocument, [draft.pk + 1]):
            PaymentDocument.objects.bulk_create([draft])


def test_document_lines_are_bounded_at_model_and_sql_boundary():
    _, _, payment = pending("r1-lines")
    draft = bill_draft(payment)
    draft.lines = [{"label": "Line", "quantity": "1", "unit_amount": "1", "total": "1"}] * 201
    with pytest.raises(ValidationError):
        draft.clean()
    with pytest.raises(DatabaseError, match="lines must reconcile"), transaction.atomic():
        PaymentDocument.objects.bulk_create([draft])


def test_bills_use_existing_notice_path_and_disabled_feature_prevents_issuance(monkeypatch):
    space, _, payment = pending("r1-bill-notice")
    calls = []
    monkeypatch.setattr("apps.payments.notifications_p2.notify_document", calls.append)
    bill = issue_bill(payment)
    assert calls == [bill]
    space.enabled_features = [key for key in space.enabled_features if key != "billing.documents"]
    space.save(update_fields=["enabled_features"])
    other = paid_deposit(space, payment.created_by, status="pending", intent="pi_no_bill")
    assert issue_bill(other) is None and len(calls) == 1
