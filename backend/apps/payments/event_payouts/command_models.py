"""Core replay receipts contain stable references, never financial PII."""
from django.conf import settings
from django.db import models


class EventPayoutCommandReceipt(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    obligation = models.ForeignKey("payments.EventPayoutObligation", on_delete=models.CASCADE, related_name="command_receipts")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    operation_id = models.UUIDField(unique=True)
    command_digest = models.CharField(max_length=64)
    response_reference = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "payments"
