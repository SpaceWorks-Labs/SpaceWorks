"""Append-only device provenance.

``*_snapshot`` fields are SOURCE-LOCAL historical values. They are deliberately not
foreign keys and never lookup keys: a tenant import keeps them byte-for-byte while the
live ``device`` FK is remapped, so a source integer can never silently rebind to an
unrelated target Machine, request or batch.
"""

import uuid

from django.db import models
from django.utils import timezone

from apps.devices.models_identity import Device
from apps.makerspaces.models import Makerspace


class DeviceEvent(models.Model):
    class EventType(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        ENROLLMENT_CREATED = "enrollment_created", "Enrollment created"
        ENROLLED = "enrolled", "Enrolled"
        ROTATION_STARTED = "rotation_started", "Rotation started"
        ROTATED = "rotated", "Rotated"
        REVOKED = "revoked", "Revoked"
        HEARTBEAT = "heartbeat", "Heartbeat"
        LABEL_COMMAND_CREATED = "label_command_created", "Label command created"
        LABEL_CONTENT_DOWNLOADED = "label_content_downloaded", "Label content downloaded"
        LABEL_COMMAND_SUCCEEDED = "label_command_succeeded", "Label command succeeded"
        LABEL_COMMAND_RETRY_SCHEDULED = "label_command_retry_scheduled", "Label command retry scheduled"
        LABEL_COMMAND_FAILED = "label_command_failed", "Label command failed"

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
