"""Source-local, single-use authority for provider PDF retrieval."""
from django.db import models


class NotificationMediaGrant(models.Model):
    delivery = models.ForeignKey("integrations.NotificationDelivery", on_delete=models.CASCADE)
    document = models.ForeignKey("payments.PaymentDocument", on_delete=models.CASCADE)
    token_digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True)
