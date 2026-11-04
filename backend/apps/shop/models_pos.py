"""Front-desk cash sessions (release 2 L22, Q-S8, Q-S19).

A session opens with a float and closes with the counted cash; the system works out the
cash it expected from the session's cash sales and cash refunds, and the variance. With
`billing.maker_checker` on, a close is only a proposal until a second person confirms it
(Q-S19: the two-person check applies to the cash-up, not to each sale). Rows never go back:
open -> (closing ->) closed, and a closed session's figures are frozen.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

MONEY = {"max_digits": 12, "decimal_places": 2}


class ShopCashSession(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSING = "closing", "Waiting for a second check"
        CLOSED = "closed", "Closed"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    currency = models.CharField(max_length=3)
    opening_float = models.DecimalField(**MONEY, default=0)
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    opened_at = models.DateTimeField(auto_now_add=True)
    counted_cash = models.DecimalField(**MONEY, null=True, blank=True)
    expected_cash = models.DecimalField(**MONEY, null=True, blank=True)
    variance = models.DecimalField(**MONEY, null=True, blank=True)
    note = models.CharField(max_length=300, blank=True, default="")
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name="+")
    closing_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                                     related_name="+")
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["makerspace"], condition=~Q(status="closed"),
                                    name="shop_cash_session_one_open"),
            models.CheckConstraint(condition=Q(opening_float__gte=0), name="shop_cash_session_float_nonnegative"),
            models.CheckConstraint(condition=~Q(status="closed") | Q(closed_at__isnull=False, counted_cash__isnull=False),
                                   name="shop_cash_session_closed_shape"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            before = type(self).objects.filter(pk=self.pk).values("status", "opening_float").first()
            if before and (before["status"] == self.Status.CLOSED or before["opening_float"] != self.opening_float):
                raise ValidationError("A closed cash session is frozen.")
        return super().save(*args, **kwargs)
