"""Source-local, single-use authority for provider PDF retrieval."""
from django.db import models


class NotificationMediaGrant(models.Model):
    delivery = models.ForeignKey("integrations.NotificationDelivery", on_delete=models.CASCADE)
    document = models.ForeignKey("payments.PaymentDocument", on_delete=models.CASCADE, null=True)
    certificate = models.ForeignKey("events.EventAttendanceCertificate", on_delete=models.CASCADE, null=True)
    storage_makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, null=True, related_name="+")
    source_revision = models.CharField(max_length=64, blank=True)
    recipient_id_snapshot = models.PositiveBigIntegerField(null=True)
    integration_generation = models.PositiveIntegerField(default=0)
    integration_identity = models.CharField(max_length=255, blank=True)
    token_digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=(
            models.Q(document__isnull=False, certificate__isnull=True)
            | models.Q(document__isnull=True, certificate__isnull=False)), name="notification_media_exact_subject")]
