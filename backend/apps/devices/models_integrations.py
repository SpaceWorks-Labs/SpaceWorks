"""Machine-integration foundations (release 2 L10; the integration itself is deferred, #76).

``MachineTypeIntegration`` binds a device integration KIND to one machine type in one
makerspace. Only ``printer_agent`` is reserved; there is no vendor adapter, so a binding
is configuration a future agent reads, nothing more. It is created disabled.

``PrinterStatusSnapshot`` is the latest bounded status a printer device sent on its
signed heartbeat: ONE row per device, overwritten in place, so its retention is the
device's own life. It is advisory telemetry and never changes ``Machine.status``, a
request, consumption or money (those move only through the machine-service workflow).
"""

from django.utils.translation import gettext_noop
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class MachineTypeIntegration(models.Model):
    class Kind(models.TextChoices):
        PRINTER_AGENT = "printer_agent", gettext_noop("Printer agent")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="machine_type_integrations")
    machine_type = models.ForeignKey("machines.MachineType", on_delete=models.CASCADE,
                                     related_name="integrations")
    kind = models.CharField(max_length=24, choices=Kind.choices)
    enabled = models.BooleanField(default=False)
    config_schema_version = models.PositiveSmallIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.UniqueConstraint(fields=("makerspace", "machine_type", "kind"),
                                    name="devices_type_integration_once"),
            models.CheckConstraint(condition=Q(config_schema_version__gte=1),
                                   name="devices_type_integration_schema_positive"),
        ]


class PrinterStatusSnapshot(models.Model):
    class State(models.TextChoices):
        IDLE = "idle", "Idle"
        PREPARING = "preparing", "Preparing"
        PRINTING = "printing", "Printing"
        PAUSED = "paused", "Paused"
        FINISHED = "finished", "Finished"
        FAILED = "failed", "Failed"
        ERROR = "error", "Error"

    device = models.OneToOneField("devices.Device", on_delete=models.CASCADE, primary_key=True,
                                  related_name="status_snapshot")
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="+")
    schema_version = models.PositiveSmallIntegerField(default=1)
    state = models.CharField(max_length=16, choices=State.choices)
    progress_percent = models.PositiveSmallIntegerField(null=True, blank=True)
    layer_current = models.PositiveIntegerField(null=True, blank=True)
    layer_total = models.PositiveIntegerField(null=True, blank=True)
    nozzle_temp_c = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    bed_temp_c = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    chamber_temp_c = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    # At most 16 {slot, material, colour, remaining_percent} objects, validated on write.
    spools = models.JSONField(default=list, blank=True)
    # The bed-cleared confirmation a future agent reports; an opaque bounded label, never a secret.
    clear_token = models.CharField(max_length=64, blank=True)
    observed_at = models.DateTimeField()
    received_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(progress_percent__isnull=True) | Q(progress_percent__lte=100),
                                   name="devices_snapshot_progress_range"),
        ]
