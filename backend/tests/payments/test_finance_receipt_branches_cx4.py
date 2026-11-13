"""Finance is core: exact ledger replay, receipt validation and screen-switch behavior."""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.audit.models import AuditLog
from apps.evidence.models import EvidencePhoto
from apps.payments import ledger_api
from apps.payments.exceptions_ledger import LedgerConflict
from apps.payments.finance_rows import money_rows
from apps.payments.models import LedgerEntry
from tests.l5_local.helpers import client, setup, switch

pytestmark = pytest.mark.django_db


def expense(space, actor, **overrides):
    data = dict(makerspace=space, domain="inventory", machine_type=None, amount="40", currency="INR",
        method="cash", reference="bill-9", receipt=None, source_kind="procurement.to_buy", source_id="9", actor=actor)
    return ledger_api.record_expense(**(data | overrides))


@pytest.mark.parametrize("change", [{"amount": "40.01"}, {"currency": "usd"}])
def test_changed_source_conflicts_without_an_extra_row_or_audit_and_void_allows_replacement(change):
    space, manager, _ = setup("cx4-finance-replay")
    first = expense(space, manager)
    assert expense(space, manager).pk == first.pk
    with pytest.raises(LedgerConflict) as conflict:
        expense(space, manager, **change)
    assert (conflict.value.status_code, conflict.value.detail["code"]) == (409, "ledger_source_conflict")
    assert LedgerEntry.objects.filter(makerspace=space).count() == 1
    assert AuditLog.objects.filter(makerspace=space, action="ledger.expense_recorded").count() == 1
    with pytest.raises(LedgerConflict) as blank:
        ledger_api.void(first, manager, "   ")
    assert (blank.value.status_code, blank.value.detail["code"]) == (409, "void_reason_required")
    ledger_api.void(first, manager, "Duplicate invoice")
    with pytest.raises(LedgerConflict) as repeated:
        ledger_api.void(first, manager, "Again")
    assert (repeated.value.status_code, repeated.value.detail["code"]) == (409, "ledger_entry_voided")
    replacement = expense(space, manager)
    assert replacement.pk != first.pk
    assert LedgerEntry.objects.filter(makerspace=space).count() == 2
    assert AuditLog.objects.filter(makerspace=space, action="ledger.entry_voided").count() == 1
    assert [(row.column, row.amount, row.row_id) for row in money_rows(space)] == [
        ("expenses", Decimal("40"), f"ledger:{replacement.pk}")]


def test_ledger_switch_hides_the_screen_but_core_recording_keeps_exact_rows_for_restoration():
    space, manager, _ = setup("cx4-finance-switch")
    foreign, other_manager, _ = setup("cx4-finance-foreign")
    expense(foreign, other_manager, amount="900")
    switch(space, "finance.ledger", on=False)
    entry = expense(space, manager)
    path = f"/api/v1/admin/makerspace/{space.pk}/finance/entries"
    refused = client(manager).get(path)
    assert (refused.status_code, refused.json()["code"]) == (404, "feature_disabled")
    assert LedgerEntry.objects.filter(makerspace=space).count() == 1
    switch(space, "finance.ledger")
    restored = client(manager).get(path)
    assert restored.status_code == 200
    assert [row["id"] for row in restored.json()["results"]] == [entry.pk]
    assert [(row.amount, row.currency) for row in money_rows(space)] == [(Decimal("40"), "inr")]


def test_foreign_receipt_is_refused_before_storage_is_consulted(monkeypatch):
    space, manager, _ = setup("cx4-finance-receipt")
    other, other_manager, _ = setup("cx4-finance-receipt-other")
    photo = EvidencePhoto.objects.create(makerspace=other, uploaded_by=other_manager, evidence_type="receipt",
                                         object_key="evidence/cx4/foreign", content_type="application/pdf")
    monkeypatch.setattr("apps.evidence.storage.finalize_upload", lambda *_: pytest.fail("foreign upload must not be read"))
    with pytest.raises(LedgerConflict) as refused:
        expense(space, manager, receipt=photo)
    assert (refused.value.status_code, refused.value.detail["code"]) == (409, "receipt_invalid")
    assert LedgerEntry.objects.count() == 0
    assert AuditLog.objects.filter(action="ledger.expense_recorded").count() == 0


@pytest.mark.parametrize("finalized,code", [
    (None, "receipt_not_uploaded"), (SimpleNamespace(size=4, content_type="image/png"), "receipt_type_mismatch")])
def test_missing_or_wrong_type_receipt_never_records_money(monkeypatch, finalized, code):
    space, manager, _ = setup("cx4-finance-invalid")
    photo = EvidencePhoto.objects.create(makerspace=space, uploaded_by=manager, evidence_type="receipt",
                                         object_key="evidence/cx4/invalid", content_type="application/pdf")
    monkeypatch.setattr("apps.evidence.storage.finalize_upload", lambda *_: finalized)
    with pytest.raises(LedgerConflict) as refused:
        expense(space, manager, receipt=photo)
    assert (refused.value.status_code, refused.value.detail["code"]) == (409, code)
    assert LedgerEntry.objects.count() == 0
    assert AuditLog.objects.filter(action="ledger.expense_recorded").count() == 0
