"""Audit presentation for the hack-money lane (#180): crew pools, booked travel, prize money, deposits.

Labels only: every emitter carries finance or participant detail, so metadata stays withheld
until someone reviews a path into the catalogue (the `event.*` namespace denies it by default).
"""
from .presentation_catalog_types import P

# Reimbursement commands (crew pool, booked travel) audit through the reviewed `ctx.audit` wrapper in
# events/staged_forms/transactions.py, so they need no entry here.
ENTRIES = (
    P("payment.event_money_settings_updated", "Prize tax and payee settings changed"),
    # Prize splits, claims and outcomes (G3-G5/G8/G16, #181 G7). Never the payee details or the PAN.
    P("event.prize.split_proposed", "Prize split proposed by the team leader"),
    P("event.prize.split_recorded", "Prize split recorded by staff"),
    P("event.prize.share_confirmed", "Prize share confirmed"),
    P("event.prize.share_declined", "Prize share declined"),
    P("event.prize.claim_submitted", "Prize payee details given"),
    P("event.prize.claim_removed", "Prize payee details removed"),
    P("event.prize.claim_verified", "Prize payee details verified"),
    P("event.prize.claim_revealed", "Prize payee details revealed to pay the winner"),
    P("event.prize.fulfilled", "Non-cash prize handed over or shipped"),
    P("event.prize.sponsor_paid", "Prize paid directly by the sponsor"),
    P("event.prize.forfeited", "Unclaimed prize forfeited"),
    P("event.prize.recovery_opened", "Prize money owed back after a disqualification"),
    P("event.prize.recovery_repaid", "Prize money repaid"),
    P("event.prize.recovery_waived", "Prize money recovery waived"),
)
