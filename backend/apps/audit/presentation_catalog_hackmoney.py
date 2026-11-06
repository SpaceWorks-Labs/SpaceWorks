"""Audit presentation for the hack-money lane (#180): crew pools, booked travel, prize money, deposits.

Labels only: every emitter carries finance or participant detail, so metadata stays withheld
until someone reviews a path into the catalogue (the `event.*` namespace denies it by default).
"""
from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P

# Reimbursement commands (crew pool, booked travel) audit through the reviewed `ctx.audit` wrapper in
# events/staged_forms/transactions.py, so they need no entry here.
ENTRIES = (
    P("payment.event_money_settings_updated", gettext_lazy("Prize tax and payee settings changed")),
    # Prize splits, claims and outcomes (G3-G5/G8/G16, #181 G7). Never the payee details or the PAN.
    P("event.prize.split_proposed", gettext_lazy("Prize split proposed by the team leader")),
    P("event.prize.split_recorded", gettext_lazy("Prize split recorded by staff")),
    P("event.prize.share_confirmed", gettext_lazy("Prize share confirmed")),
    P("event.prize.share_declined", gettext_lazy("Prize share declined")),
    P("event.prize.claim_submitted", gettext_lazy("Prize payee details given")),
    P("event.prize.claim_removed", gettext_lazy("Prize payee details removed")),
    P("event.prize.claim_verified", gettext_lazy("Prize payee details verified")),
    P("event.prize.claim_revealed", gettext_lazy("Prize payee details revealed to pay the winner")),
    P("event.prize.fulfilled", gettext_lazy("Non-cash prize handed over or shipped")),
    P("event.prize.sponsor_paid", gettext_lazy("Prize paid directly by the sponsor")),
    P("event.prize.forfeited", gettext_lazy("Unclaimed prize forfeited")),
    P("event.prize.recovery_opened", gettext_lazy("Prize money owed back after a disqualification")),
    P("event.prize.recovery_repaid", gettext_lazy("Prize money repaid")),
    P("event.prize.recovery_waived", gettext_lazy("Prize money recovery waived")),
    # Deposits (G10). Raising and closing go through the reviewed programme-charge wrapper.
    P("event.deposit.settled", gettext_lazy("Event deposits settled by staff")),
    P("event.deposit.forfeited", gettext_lazy("Deposit kept after a no-show")),
)
