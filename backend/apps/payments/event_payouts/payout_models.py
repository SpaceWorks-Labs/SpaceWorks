"""An immutable record that a human already paid, with replacement corrections."""

from uuid import uuid4
from django.conf import settings
from django.db import models
from .model_base import Immutable
from .validation import METHODS


class EventPayoutEntry(Immutable):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    obligation = models.ForeignKey("payments.EventPayoutObligation", on_delete=models.CASCADE, related_name="entries")
    payee_revision = models.ForeignKey("payments.EventPayeeRevision", on_delete=models.CASCADE, null=True, related_name="entries")
    eligibility_revision = models.PositiveBigIntegerField()
    amount_minor = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3)
    method = models.CharField(max_length=16, choices=[(v, v) for v in sorted(METHODS)])
    reference = models.CharField(max_length=64)
    paid_at = models.DateTimeField()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recorded_event_payouts")
    recorded_at = models.DateTimeField(auto_now_add=True)
    operation_id = models.UUIDField(unique=True)
    command_digest = models.CharField(max_length=64)
    chain_uuid = models.UUIDField(default=uuid4)
    amends = models.OneToOneField("self", on_delete=models.CASCADE, null=True, related_name="amended_by")
    reason_code = models.CharField(max_length=64, blank=True)
    is_void = models.BooleanField(default=False)

    class Meta:
        app_label = "payments"
        constraints = [
            models.CheckConstraint(condition=(models.Q(is_void=False, amount_minor__gt=0)
                | models.Q(is_void=True, amount_minor=0, amends__isnull=False)), name="payout_entry_void_shape"),
            models.CheckConstraint(condition=(models.Q(amends__isnull=True) | ~models.Q(reason_code="")), name="payout_amend_reason"),
        ]
