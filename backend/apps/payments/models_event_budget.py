"""A per-event finance budget (X55): append-only revisions, the newest per currency wins.

Kept in the core ledger rather than on the event so a budget, like the money it is
measured against, survives an events tombstone and an event purge (the FK is SET_NULL
and the id/title snapshots keep the row readable).
"""

from django.utils.translation import gettext
from django.core.exceptions import ValidationError
from django.db import models

from apps.payments.models_settings import currency_validator
from apps.payments.money_model import MoneyDecimalField


class EventFinanceBudget(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    event_id_snapshot = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3, validators=[currency_validator])
    amount = MoneyDecimalField(max_digits=13, decimal_places=3)
    set_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    set_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-set_at", "-pk"]
        constraints = [models.CheckConstraint(condition=models.Q(amount__gte=0), name="event_budget_not_negative")]
        indexes = [models.Index(fields=["makerspace", "event_id_snapshot"], name="event_budget_lookup_idx")]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(gettext("Event budgets are revised by appending a new row."))
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(gettext("Event budgets are revised by appending a new row."))


def effective_budgets(makerspace_id, event_ids=None):
    """{(event_id, currency): amount} from the newest revision of each."""
    rows = EventFinanceBudget.objects.filter(makerspace_id=makerspace_id)
    if event_ids is not None:
        rows = rows.filter(event_id_snapshot__in=list(event_ids))
    budgets = {}
    for row in rows.order_by("-set_at", "-pk").values_list("event_id_snapshot", "currency", "amount"):
        budgets.setdefault((row[0], row[1]), row[2])
    return budgets
