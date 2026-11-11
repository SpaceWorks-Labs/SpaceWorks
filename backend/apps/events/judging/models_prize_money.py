"""Hack-money (#180, #181) prize money beyond the L21b payout row.

- `HackathonPrizeShare` (G3/G4): who on a winning team is owed what. One row per member per award.
  The leader proposes a split and each member confirms in the app, or staff record it already
  confirmed. With no shares the L21b default stands: one payout, to the leader. Each share is one
  payee: it is paid by its own payout row and, for prize tax (G7), crosses the threshold on its own.
- `HackathonPrizeClaim` (G4/G7): the payee details and the tax ID a share's member gives. Its own
  row, like L18's `DonorTaxDetail`, so only writing it needs the tenant key. `details` and `pan` are
  mandatory-encrypted scoped PII; they are masked everywhere and never enter audit, exports or
  analytics. Cleared once the share is paid or forfeited.
- `HackathonPrizeOutcome` (G4/G5/G8/G16): append-only facts about an award that are not a payout:
  a non-cash prize handed over or shipped, a prize the sponsor paid directly, a forfeited prize after
  the claim window, and money owed back after a post-payout disqualification (opened, repaid,
  waived). Only `recovery_repaid` touches the ledger (a receipt); nothing here ever moves money.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.encryption.mappers import ScopedPiiModelMixin

from .models_base import AppendOnly, EventOwned
from apps.payments.money_model import MoneyDecimalField

SHARE_STATES = ("proposed", "confirmed", "declined", "forfeited")
OUTCOME_KINDS = ("fulfilled", "sponsor_paid", "forfeited", "recovery_opened", "recovery_repaid", "recovery_waived")


class HackathonPrizeShare(EventOwned):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    award = models.ForeignKey("events.EventAward", on_delete=models.PROTECT, related_name="+")
    member = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    amount = MoneyDecimalField(max_digits=13, decimal_places=3)
    state = models.CharField(max_length=12, default="proposed", choices=[(v, v) for v in SHARE_STATES])
    proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="ev_prize_share_amount"),
            models.CheckConstraint(condition=Q(state__in=SHARE_STATES), name="ev_prize_share_state"),
            models.UniqueConstraint(fields=("award", "member"), name="ev_prize_share_member"),
        ]


class HackathonPrizeClaim(ScopedPiiModelMixin, EventOwned):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    share = models.OneToOneField(HackathonPrizeShare, on_delete=models.CASCADE, related_name="claim")
    country = models.CharField(max_length=2, blank=True)
    method = models.CharField(max_length=16, blank=True)
    template_key = models.CharField(max_length=24, blank=True)
    details = models.TextField(blank=True, default="")
    pan = models.TextField(blank=True, default="")
    submitted_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    cleared_at = models.DateTimeField(null=True, blank=True)


class HackathonPrizeOutcome(AppendOnly):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="+")
    # Null only on a People's choice recovery (#181), which names the payout of a winning standing instead.
    award = models.ForeignKey("events.EventAward", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    share = models.ForeignKey(HackathonPrizeShare, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    payout = models.ForeignKey("events.HackathonPrizePayout", null=True, blank=True, on_delete=models.PROTECT,
                               related_name="+")
    resolves = models.OneToOneField("self", null=True, blank=True, on_delete=models.PROTECT, related_name="resolution")
    kind = models.CharField(max_length=16, choices=[(v, v) for v in OUTCOME_KINDS])
    method = models.CharField(max_length=16, blank=True)
    reference = models.CharField(max_length=64, blank=True)
    amount = MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    happened_on = models.DateField()
    note = models.CharField(max_length=300, blank=True)
    ledger_entry = models.ForeignKey("payments.LedgerEntry", null=True, blank=True, on_delete=models.PROTECT,
                                     related_name="+")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(kind__in=OUTCOME_KINDS), name="ev_prize_outcome_kind"),
            models.CheckConstraint(condition=Q(amount__isnull=True) | Q(amount__gt=0), name="ev_prize_outcome_amount"),
            models.CheckConstraint(condition=(Q(kind__in=("recovery_repaid", "recovery_waived"), resolves__isnull=False)
                                              | (~Q(kind__in=("recovery_repaid", "recovery_waived"))
                                                 & Q(resolves__isnull=True))), name="ev_prize_outcome_resolves"),
            models.CheckConstraint(condition=Q(ledger_entry__isnull=True) | Q(kind="recovery_repaid"),
                                   name="ev_prize_outcome_ledger"),
            models.CheckConstraint(condition=Q(award__isnull=False) | (Q(payout__isnull=False) & Q(
                kind__in=("recovery_opened", "recovery_repaid", "recovery_waived"))), name="ev_prize_outcome_subject"),
        ]
