"""Audit presentation for the hack-money lane (#180): crew pools, booked travel, prize money, deposits.

Labels only: every emitter carries finance or participant detail, so metadata stays withheld
until someone reviews a path into the catalogue (the `event.*` namespace denies it by default).
"""
from .presentation_catalog_types import P

# Reimbursement commands (crew pool, booked travel) audit through the reviewed `ctx.audit` wrapper in
# events/staged_forms/transactions.py, so they need no entry here.
ENTRIES = (
)
