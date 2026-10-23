from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class EventRegistrationCredential(models.Model):
    registration = models.ForeignKey("events.EventRegistration", on_delete=models.CASCADE,
                                     related_name="credentials")
    generation = models.PositiveIntegerField()
    token_digest = models.CharField(max_length=64, unique=True, editable=False)
    token_ciphertext = models.BinaryField(editable=False)
    key_version = models.PositiveIntegerField(editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name="+")
    revocation_reason = models.CharField(max_length=32, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("registration", "generation"), name="event_credential_generation"),
            models.UniqueConstraint(fields=("registration",), condition=Q(revoked_at__isnull=True),
                                    name="event_credential_live"),
            models.CheckConstraint(condition=Q(generation__gt=0), name="event_credential_generation_positive"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.get(pk=self.pk)
            frozen = ("registration_id", "generation", "token_digest", "token_ciphertext",
                      "key_version", "created_at", "expires_at")
            if old.revoked_at or any(getattr(old, key) != getattr(self, key) for key in frozen):
                raise ValidationError("Credential generations are immutable; rotate instead.")
        return super().save(*args, **kwargs)


class EventCredentialCommand(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE)
    operation_id = models.UUIDField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    request_sha256 = models.CharField(max_length=64)
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("event", "operation_id"), name="event_credential_command")]
