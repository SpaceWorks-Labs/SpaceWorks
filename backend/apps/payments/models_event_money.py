"""Hack-money per-space event money settings (#180 G13, #181 G7). Space Manager only, never delegable.

- Prize tax (G7, RECORD ONLY): when on, a prize payout above the threshold PROPOSES tax deducted at
  source at the rate; staff confirm or change it when recording, deduct it and file it outside
  SpaceWorks. No certificates and no filing reports are produced. Off by default.
- Payee templates (G13): which payee country/method pairs this space accepts for event payouts and
  prize claims, inside the deployment ceiling. Empty keeps the operator's per-host policy as it is.
"""

from decimal import Decimal

from django.db import models
from django.db.models import Q
from apps.payments.money_model import MoneyDecimalField


class EventMoneySettings(models.Model):
    makerspace = models.OneToOneField("makerspaces.Makerspace", on_delete=models.CASCADE,
                                      related_name="event_money_settings")
    prize_tds_enabled = models.BooleanField(default=False)
    prize_tds_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("30.00"))
    prize_tds_threshold = MoneyDecimalField(max_digits=13, decimal_places=3, default=Decimal("10000.00"))
    payee_templates = models.JSONField(default=list, blank=True)
    version = models.PositiveIntegerField(default=1)
    updated_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(prize_tds_rate__gte=0, prize_tds_rate__lte=100), name="event_money_tds_rate"),
            models.CheckConstraint(condition=Q(prize_tds_threshold__gte=0), name="event_money_tds_threshold"),
        ]

    @classmethod
    def for_makerspace(cls, makerspace):
        row = cls.objects.filter(makerspace=makerspace).first()
        return row if row is not None else cls(makerspace=makerspace, version=0)
