"""A superadmin's audited, time-boxed window onto one space's (or one person's) PII.

Owner decisions #110e and #111 Q12: a platform superadmin sees members' PII masked until
they open a 30-minute window with a reason and recent re-authentication. A window covers
either one makerspace, or one person across every space they belong to (the per-person
reveal in /control/ user admin). Rows are append-only: the only update ever made is the
one-way close (``closed_at`` and ``close_reason``), by hand or at expiry.
"""

import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

WINDOW = timedelta(minutes=30)


class PlatformPiiAccessGrant(models.Model):
    class CloseReason(models.TextChoices):
        CLOSED = "closed", "Closed"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    makerspace = models.ForeignKey(
        "makerspaces.Makerspace", on_delete=models.CASCADE, null=True, blank=True, related_name="+",
    )
    subject = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="+",
    )
    reason = models.CharField(max_length=300, validators=[MinLengthValidator(10)])
    opened_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)
    close_reason = models.CharField(max_length=16, choices=CloseReason.choices, blank=True, default="")

    class Meta:
        ordering = ("-opened_at",)
        indexes = [models.Index(fields=("actor", "expires_at"), name="pii_grant_actor_expiry")]
        constraints = [
            models.CheckConstraint(
                condition=Q(makerspace__isnull=False) | Q(subject__isnull=False), name="pii_grant_has_scope",
            ),
            models.CheckConstraint(condition=Q(expires_at__gt=models.F("opened_at")), name="pii_grant_expires_after_open"),
        ]

    def is_active(self, now=None):
        now = now or timezone.now()
        return self.closed_at is None and self.opened_at <= now < self.expires_at

    def save(self, *args, **kwargs):
        if not self._state.adding:
            stored = type(self).objects.filter(pk=self.pk).values("closed_at").first()
            fields = set(kwargs.get("update_fields") or ())
            if stored is None or stored["closed_at"] is not None or fields != {"closed_at", "close_reason"}:
                raise ValidationError("PII access grants are append-only; only an open grant may be closed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("PII access grants are never deleted.")
