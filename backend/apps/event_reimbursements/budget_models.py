"""Budget checks provide a database backstop to budget_service arithmetic."""

from django.conf import settings
from django.db import models
from .model_base import Immutable, Versioned


class ReimbursementBudgetPool(Versioned):
    programme = models.ForeignKey("event_reimbursements.ReimbursementProgramme", on_delete=models.CASCADE,
                                 related_name="pools")
    currency = models.CharField(max_length=3)
    # Hack-money G14: an optional second pool that only crew awards reserve from.
    audience = models.CharField(max_length=12, default="participants",
                                choices=[(v, v) for v in ("participants", "crew")])
    total_minor = models.PositiveBigIntegerField(default=0)
    reserved_minor = models.PositiveBigIntegerField(default=0)
    committed_minor = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("programme", "currency", "audience"), name="reimb_unique_pool_audience"),
            models.CheckConstraint(condition=models.Q(audience__in=("participants", "crew")), name="reimb_pool_audience"),
            models.CheckConstraint(condition=models.Q(total_minor__gte=models.F("reserved_minor")
                + models.F("committed_minor")), name="reimb_budget_never_overdrawn"),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="reimb_pool_version_positive"),
        ]


class BudgetReservation(Versioned):
    pool = models.ForeignKey(ReimbursementBudgetPool, on_delete=models.CASCADE, related_name="reservations")
    award = models.OneToOneField("event_reimbursements.GrantAward", on_delete=models.CASCADE,
                                related_name="reservation")
    state = models.CharField(max_length=12, default="held", choices=[(v, v) for v in ("held", "committed", "released")])
    held_minor = models.PositiveBigIntegerField(default=0)
    committed_minor = models.PositiveBigIntegerField(default=0)
    decision = models.ForeignKey("event_reimbursements.ClaimDecision", on_delete=models.SET_NULL, null=True,
                                related_name="+")
    released_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=(~models.Q(state="released")
            | models.Q(held_minor=0, committed_minor=0)), name="reimb_released_reservation_empty")]


class BudgetEntry(Immutable):
    pool = models.ForeignKey(ReimbursementBudgetPool, on_delete=models.CASCADE, related_name="entries")
    operation_id = models.UUIDField()
    kind = models.CharField(max_length=20, choices=[(v, v) for v in (
        "fund", "reserve", "release", "commit", "adjust_commitment")])
    amount_minor = models.BigIntegerField()
    reservation = models.ForeignKey(BudgetReservation, on_delete=models.CASCADE, null=True, related_name="entries")
    decision = models.ForeignKey("event_reimbursements.ClaimDecision", on_delete=models.CASCADE,
                                null=True, related_name="budget_entries")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    reason_code = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("pool", "operation_id", "kind", "reservation"),
                                    nulls_distinct=False, name="reimb_budget_entry_operation"),
            models.CheckConstraint(condition=(models.Q(kind="fund", reservation__isnull=True, decision__isnull=True)
                | models.Q(kind__in=("reserve", "release"), reservation__isnull=False, decision__isnull=True)
                | models.Q(kind__in=("commit", "adjust_commitment"), reservation__isnull=False)),
                name="reimb_budget_entry_shape"),
        ]
