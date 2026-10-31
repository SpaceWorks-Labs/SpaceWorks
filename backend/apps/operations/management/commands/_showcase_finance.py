"""Tinkerspace finance ledger: a few months of spending and other income (lane L5).

Written through `payments.ledger_api`, exactly like the lanes that record spending, so
the income-versus-spending report, the per-area views and the FY bookkeeping all have
something to show. Tax stays off (the default); an opening balance starts the books.
"""

from datetime import timedelta
from decimal import Decimal

from apps.makerspaces.local_time import local_now
from apps.payments import ledger_api
from apps.payments.ledger_entries import set_opening_balance

EXPENSES = (
    ("inventory", "to_buy", "45.00", "cash", "Soldering tips and flux", "Maker Supplies Co", 70),
    ("machines", "maintenance", "120.00", "bank_transfer", "Laser tube alignment service", "Beam Services", 40),
    ("general", "rent", "900.00", "bank_transfer", "Workshop rent", "Harbour Lofts", 30),
    ("bookings", "repair", "60.00", "card", "Meeting-room projector bulb", "AV Depot", 12),
    ("events", "events", "35.00", "upi", "Repair cafe refreshments", "Corner Bakery", 5),
)


def seed_finance(space, manager):
    today = local_now(space).date()
    set_opening_balance(actor=manager, makerspace=space, fy_start_date=today, currency="usd",
                        cash_amount=Decimal("150.00"), bank_amount=Decimal("2400.00"))
    for index, (domain, category, amount, method, description, counterparty, days) in enumerate(EXPENSES):
        ledger_api.record_expense(space, domain, None, amount, "usd", method, f"TS-EXP-{index + 1:03d}", None,
                                  "showcase.seed", f"expense-{index + 1}", manager, category=category,
                                  description=description, counterparty=counterparty,
                                  entry_date=today - timedelta(days=days))
    ledger_api.record_receipt(space, "donations", None, "250.00", "usd", "bank_transfer", "TS-DON-001", None,
                              "showcase.seed", "donation-1", manager, category="donation",
                              description="Community fund donation", counterparty="Harbour Rotary Club",
                              entry_date=today - timedelta(days=20))
