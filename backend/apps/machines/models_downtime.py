"""The downtime ledger (machines D7, MT6): one row per out-of-service period.

Opened when a machine goes to maintenance or offline, closed once when it comes back.
Append-only otherwise: the reason and expected-back date may be updated while the
period is open (staff learn more), never after it closes, and a row is never deleted.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class MachineDowntime(models.Model):
    class Kind(models.TextChoices):
        MAINTENANCE = "maintenance", "Maintenance"
        OFFLINE = "offline", "Offline"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="machine_downtimes")
    machine = models.ForeignKey("machines.Machine", on_delete=models.CASCADE, related_name="downtimes")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    reason = models.CharField(max_length=300, blank=True)
    expected_back_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    started_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    ended_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="+")

    class Meta:
        ordering = ["-started_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["machine"], condition=Q(ended_at__isnull=True),
                                    name="machine_downtime_one_open"),
            models.CheckConstraint(condition=Q(ended_at__isnull=True) | Q(ended_at__gte=models.F("started_at")),
                                   name="machine_downtime_ends_after_start"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            closed = type(self).objects.filter(pk=self.pk, ended_at__isnull=False).exists()
            if closed:
                raise ValidationError("A closed downtime period is final.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Downtime periods are never deleted.")
