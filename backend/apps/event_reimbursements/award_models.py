"""Offers reserve funds; accepted award caps are immutable workflow evidence."""

from uuid import uuid4
from django.conf import settings
from django.db import models
from apps.encryption.mappers import ScopedPiiModelMixin
from .model_base import Immutable, Versioned


class GrantAward(ScopedPiiModelMixin, Versioned):
    uuid = models.UUIDField(default=uuid4, unique=True, editable=False)
    request = models.OneToOneField("event_reimbursements.GrantRequest", on_delete=models.CASCADE, related_name="award")
    pool = models.ForeignKey("event_reimbursements.ReimbursementBudgetPool", on_delete=models.CASCADE, related_name="awards")
    state = models.CharField(max_length=12, default="offered", choices=[(v, v) for v in (
        "offered", "accepted", "forfeited", "expired", "closed")])
    due_revision = models.PositiveBigIntegerField(default=1)
    amount_minor = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3)
    rule_revision = models.PositiveBigIntegerField()
    calculation_snapshot = models.JSONField(default=dict)
    accept_by = models.DateTimeField()
    offered_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True)
    closed_at = models.DateTimeField(null=True)
    reason_code = models.CharField(max_length=64, blank=True)
    note = models.TextField(blank=True)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(amount_minor__gt=0), name="reimb_award_positive")]


class GrantAwardRevision(Immutable):
    award = models.ForeignKey(GrantAward, on_delete=models.CASCADE, related_name="revisions")
    revision = models.PositiveBigIntegerField()
    amount_minor = models.PositiveBigIntegerField()
    rule_snapshot = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    reason_code = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("award", "revision"), name="reimb_award_revision_unique"),
            models.CheckConstraint(condition=models.Q(amount_minor__gt=0, revision__gte=1), name="reimb_award_revision_bounds"),
        ]
