"""X22 / #94 / #100: the finance ledger records every movement and shows each area its own."""

from datetime import date
from decimal import Decimal

import pytest
from django.db import DatabaseError, transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.machines.models import MachineType
from apps.payments import ledger_api
from apps.payments.exceptions_ledger import LedgerConflict
from apps.payments.finance_rows import money_rows
from apps.payments.models import LedgerEntry
from apps.payments.reconciliation import mark_offline
from apps.payments.reports_finance_ledger import build_income_spending
from apps.payments.services_refunds_offline import record_offline_refund
from tests.l5_local.helpers import client, dues, setup, staff, switch
from tests.return_helpers import settlement_details

pytestmark = pytest.mark.django_db
D = Decimal


def _expense(space, actor, domain="inventory", source="1", amount="40.00", **extra):
    return ledger_api.record_expense(space, domain, extra.pop("machine_type", None), amount, "inr", "cash", "R-1",
                                     None, "procurement.to_buy", source, actor, category="to_buy", **extra)


def test_record_expense_is_idempotent_per_source_and_audited():
    space, manager, _payer = setup("ledger-api")
    first = _expense(space, manager)
    assert _expense(space, manager) == first
    with pytest.raises(LedgerConflict) as exc:
        _expense(space, manager, amount="41.00")
    assert exc.value.detail["code"] == "ledger_source_conflict"
    assert first.account == "cash"
    assert AuditLog.objects.filter(action="ledger.expense_recorded", target_id=str(first.pk)).exists()


def test_void_keeps_the_row_and_database_refuses_edits_and_deletes():
    space, manager, _payer = setup("ledger-void")
    entry = _expense(space, manager)
    ledger_api.void(entry, manager, "Bought twice by mistake")
    entry.refresh_from_db()
    assert entry.voided_at and entry.void_reason
    with pytest.raises(LedgerConflict):
        ledger_api.void(entry, manager, "again")
    with pytest.raises(DatabaseError), transaction.atomic():
        LedgerEntry.objects.filter(pk=entry.pk).update(amount=D("1.00"))
    with pytest.raises(DatabaseError), transaction.atomic():
        LedgerEntry.objects.filter(pk=entry.pk).delete()
    # A voided purchase may be recorded again for the same source.
    assert _expense(space, manager).pk != entry.pk


def test_spending_is_recorded_even_with_the_ledger_screens_off():
    space, manager, _payer = setup("ledger-off")
    switch(space, "finance.ledger", on=False)
    _expense(space, manager)
    assert LedgerEntry.objects.filter(makerspace=space).count() == 1
    assert client(manager).get(f"/api/v1/admin/makerspace/{space.pk}/finance/entries").status_code == 404
    switch(space, "finance.ledger")
    assert client(manager).get(f"/api/v1/admin/makerspace/{space.pk}/finance/entries").json()["count"] == 1


def test_every_movement_lands_in_income_versus_spending():
    space, manager, payer = setup("ledger-sum", "finance.ledger")
    charge = dues(space, payer, "100.00")
    mark_offline(charge, manager, settlement_details(reference="CASH-9"))
    charge.refresh_from_db()
    record_offline_refund(charge, amount="30.00", reason="Partly unused", actor=manager, receipt={
        "method": "cash", "reference": "R-9", "refunded_at": timezone.now().isoformat()})
    _expense(space, manager, amount="40.00")
    ledger_api.record_receipt(space, "donations", None, "25.00", "inr", "upi", "UTR1", None, "manual", "",
                              manager, category="donation")
    columns = {}
    for row in money_rows(space):
        columns[row.column] = columns.get(row.column, D(0)) + row.amount
    assert columns == {"income": D("100.00"), "refunds": D("30.00"), "expenses": D("40.00"),
                       "other_income": D("25.00")}
    totals = build_income_spending(space.pk).records
    assert sum(row["net"] for row in totals) == D("55.00")


def test_each_area_manager_sees_only_their_area_and_machine_types():
    space, manager, _payer = setup("ledger-areas", "finance.ledger")
    printer, laser = MachineType.objects.create(name="L5 printer", slug="l5-printer", makerspace=space),         MachineType.objects.create(name="L5 laser", slug="l5-laser", makerspace=space)
    _expense(space, manager, domain="inventory", source="inv")
    _expense(space, manager, domain="machines", source="mac", machine_type=printer)
    _expense(space, manager, domain="machines", source="las", machine_type=laser)
    _expense(space, manager, domain="bookings", source="room")
    inventory = staff("ledger-areas", space, "inventory_manager")
    booking = staff("ledger-areas", space, "booking_manager")
    url = f"/api/v1/admin/makerspace/{space.pk}/finance/entries"
    assert {row["domain"] for row in client(inventory).get(url).json()["results"]} == {"inventory"}
    assert {row["domain"] for row in client(booking).get(url).json()["results"]} == {"bookings"}
    assert client(manager).get(url).json()["count"] == 4
    member = staff("ledger-areas", space, "member")
    assert client(member).get(url).status_code in (403, 404)
    # An inventory manager cannot record machine spending.
    response = client(inventory).post(url, {
        "kind": "expense", "domain": "machines", "category": "repair", "method": "cash", "amount": "5.00",
        "currency": "inr", "entry_date": date.today().isoformat(), "description": "Belt"}, format="json")
    assert response.status_code == 403


def test_manual_entry_and_void_through_the_api():
    space, manager, _payer = setup("ledger-http", "finance.ledger")
    api = client(manager)
    created = api.post(f"/api/v1/admin/makerspace/{space.pk}/finance/entries", {
        "kind": "expense", "domain": "general", "category": "rent", "method": "bank_transfer",
        "amount": "1200.00", "currency": "inr", "entry_date": "2026-10-01", "description": "October rent"},
        format="json")
    assert created.status_code == 201 and created.json()["account"] == "bank"
    entry_id = created.json()["id"]
    voided = api.post(f"/api/v1/admin/makerspace/{space.pk}/finance/entries/{entry_id}/void",
                      {"reason": "Wrong month"}, format="json")
    assert voided.status_code == 200 and voided.json()["voided_at"]
    summary = api.get(f"/api/v1/admin/makerspace/{space.pk}/finance/summary").json()
    assert all(row["expenses"] == "0.00" for row in summary["rows"])


def test_opening_balances_are_append_only_revisions():
    space, manager, _payer = setup("ledger-open", "finance.ledger")
    api = client(manager)
    url = f"/api/v1/admin/makerspace/{space.pk}/finance/opening-balances"
    for cash in ("10.00", "15.00"):
        assert api.put(url, {"fy_start": "2026-04-01", "currency": "inr", "cash_amount": cash,
                             "bank_amount": "0"}, format="json").status_code == 200
    rows = api.get(url, {"fy": "2026-06-01"}).json()
    assert [row["cash_amount"] for row in rows] == ["15.00"]
