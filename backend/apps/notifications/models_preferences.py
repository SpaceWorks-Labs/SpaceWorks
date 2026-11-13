"""Personal multi-select policy; distinct from integrations' tenant matrix."""
from django.conf import settings
from django.db import models


class NotificationPreference(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.CharField(max_length=32)
    channels = models.JSONField(default=list)
    email_fallback = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["makerspace", "user", "category"], name="uniq_personal_channel_selection")]
