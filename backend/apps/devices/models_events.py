"""Append-only device provenance.

``*_snapshot`` fields are SOURCE-LOCAL historical values. They are deliberately not
foreign keys and never lookup keys: a tenant import keeps them byte-for-byte while the
live ``device`` FK is remapped, so a source integer can never silently rebind to an
unrelated target Machine, request or batch.
"""

from django.utils.translation import gettext_lazy
import uuid

from django.db import models
from django.utils import timezone

from apps.devices.models_identity import Device
from apps.makerspaces.models import Makerspace


class DeviceEvent(models.Model):
    class EventType(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        ENROLLMENT_CREATED = "enrollment_created", gettext_lazy("Enrollment created")
        ENROLLED = "enrolled", "Enrolled"
        ROTATION_STARTED = "rotation_started", gettext_lazy("Rotation started")
        ROTATED = "rotated", "Rotated"
        REVOKED = "revoked", "Revoked"
        HEARTBEAT = "heartbeat", "Heartbeat"
        PRINTER_BOUND = "printer_bound", gettext_lazy("printer bound")
        PRINTER_UNBOUND = "printer_unbound", gettext_lazy("printer unbound")
        PRINTER_JOB_CREATED = "printer_job_created", gettext_lazy("printer job created")
        COMMAND_LEASED = "command_leased", gettext_lazy("command leased")
        COMMAND_ACKNOWLEDGED = "command_acknowledged", gettext_lazy("command acknowledged")
        COMMAND_DELIVERY_FAILED = "command_delivery_failed", gettext_lazy("command delivery failed")
        PRINTER_TELEMETRY_RECEIVED = "printer_telemetry_received", gettext_lazy("printer telemetry received")
        PRINTER_RESULT_CLAIMED = "printer_result_claimed", gettext_lazy("printer result claimed")
        PRINTER_RESULT_APPLIED = "printer_result_applied", gettext_lazy("printer result applied")
        PRINTER_RESULT_NEEDS_REVIEW = "printer_result_needs_review", gettext_lazy("printer result needs review")
        PRINTER_JOB_CANCELLED = "printer_job_cancelled", gettext_lazy("printer job cancelled")
        LABEL_COMMAND_CREATED = "label_command_created", gettext_lazy("Label command created")
        LABEL_CONTENT_DOWNLOADED = "label_content_downloaded", gettext_lazy("Label content downloaded")
        LABEL_COMMAND_SUCCEEDED = "label_command_succeeded", gettext_lazy("Label command succeeded")
        LABEL_COMMAND_RETRY_SCHEDULED = "label_command_retry_scheduled", gettext_lazy("Label command retry scheduled")
        LABEL_COMMAND_FAILED = "label_command_failed", gettext_lazy("Label command failed")
        OFFLINE = "offline_detected", gettext_lazy("Offline detected")
        RECOVERED = "recovered", "Recovered"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    makerspace = models.ForeignKey(
        Makerspace, on_delete=models.CASCADE, related_name="device_events"
    )
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="events")
    device_id_snapshot = models.CharField(max_length=36)
    device_name = models.CharField(max_length=120)
    device_key_version = models.PositiveIntegerField()
    operation_id = models.UUIDField(default=uuid.uuid4)
    event_type = models.CharField(max_length=32, choices=EventType.choices)
    outcome = models.CharField(max_length=32, default="ok")
    command_id_snapshot = models.UUIDField(null=True, blank=True)
    machine_id_snapshot = models.PositiveBigIntegerField(null=True, blank=True)
    service_request_id_snapshot = models.PositiveBigIntegerField(null=True, blank=True)
    qr_batch_id_snapshot = models.PositiveBigIntegerField(null=True, blank=True)
    # Allowlisted, credential-free scalars only (see services_events.ALLOWED_DETAIL_KEYS).
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["device", "created_at"])]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("DeviceEvent rows are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("DeviceEvent rows are append-only.")
