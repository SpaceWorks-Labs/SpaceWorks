"""L21b (C-38): prize payouts recorded by hand. Append-only; a mistake is corrected by a reversal row.

Each payout row owns one L5 ledger expense (domain `events`, category `prize`); its reversal voids that
expense. Nothing here moves money: staff record that they paid a winner.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

from .models_base import AppendOnly


class HackathonPrizePayout(AppendOnly):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="+")
    # A judged award, or (#181) a People's choice winning standing: exactly one of the two.
    award = models.ForeignKey("events.EventAward", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    peoples_choice_standing = models.ForeignKey("events.PeoplesChoiceStanding", null=True, blank=True,
                                                on_delete=models.PROTECT, related_name="+")
    prize = models.ForeignKey("events.HackathonPrize", on_delete=models.PROTECT, related_name="+")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    kind = models.CharField(max_length=8, default="payout", choices=(("payout", "Payout"), ("reversal", "Reversal")))
    reverses = models.OneToOneField("self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversal")
    amount = models.DecimalField(max_digits=12, decimal_places=2)  # gross: the ledger expense
    # Hack-money G7 (#181, record only): tax deducted at source and what reached the winner.
    tds_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3)
    method = models.CharField(max_length=16)
    reference = models.CharField(max_length=64, blank=True)
    paid_on = models.DateField()
    ledger_entry = models.ForeignKey("payments.LedgerEntry", on_delete=models.PROTECT, related_name="+")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="ev_payout_amount_positive"),
            models.CheckConstraint(condition=Q(tds_amount__gte=0, tds_amount__lt=models.F("amount")), name="ev_payout_tds_bounds"),
            models.CheckConstraint(condition=Q(net_amount__isnull=True) | Q(net_amount=models.F("amount") - models.F("tds_amount")),
                                   name="ev_payout_net_shape"),
            models.CheckConstraint(condition=Q(kind__in=("payout", "reversal")), name="ev_payout_kind"),
            models.CheckConstraint(condition=(Q(kind="payout") & Q(reverses__isnull=True))
                                   | (Q(kind="reversal") & Q(reverses__isnull=False)), name="ev_payout_reversal_shape"),
            models.CheckConstraint(condition=Q(award__isnull=False, peoples_choice_standing__isnull=True)
                                   | Q(award__isnull=True, peoples_choice_standing__isnull=False), name="ev_payout_one_award"),
        ]
