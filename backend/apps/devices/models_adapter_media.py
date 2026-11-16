"""Device Adapter API media and data state (decision 321): artifacts, telemetry history, remote config, offline cache.

All device-bound operational data: OMITTED from exports and tenant dumps (see ``data_export/classification_adapter``).
Artifact BYTES are private objects under ``adapter-artifacts/``; the row keeps the key, the kind and the expiry, and the
retention sweep deletes the bytes (rows stay as a purged marker). Telemetry is bounded by its rollup sweep.
"""
import uuid

from django.utils.translation import gettext_noop
from django.conf import settings
from django.db import models
from django.utils import timezone

from .models_adapter import AdapterBinding


class AdapterArtifact(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", gettext_noop("Pending upload")
        READY = "ready", "Ready"
        PURGED = "purged", "Purged"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    binding = models.ForeignKey(AdapterBinding, on_delete=models.CASCADE, related_name="artifacts")
    operation_id = models.UUIDField()
    kind = models.CharField(max_length=20)
    content_type = models.CharField(max_length=64)
    size_bytes = models.PositiveBigIntegerField()
    object_key = models.CharField(max_length=200)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    # Links to what the artifact belongs to; plain ids (a request/session may be purged independently).
    service_request_id = models.PositiveBigIntegerField(null=True, blank=True)
    session_id = models.PositiveBigIntegerField(null=True, blank=True)
    command_id = models.UUIDField(null=True, blank=True)
    captured_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    purged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["binding", "kind", "created_at"], name="adapter_artifact_binding_idx"),
                   models.Index(fields=["status", "expires_at"], name="adapter_artifact_expiry_idx")]
        constraints = [models.UniqueConstraint(fields=("binding", "operation_id"), name="adapter_artifact_once")]


class AdapterTelemetryPoint(models.Model):
    """One series sample. resolution 0 = raw, 60 = one-minute rollup, 900 = fifteen-minute rollup."""

    id = models.BigAutoField(primary_key=True)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    binding = models.ForeignKey(AdapterBinding, on_delete=models.CASCADE, related_name="telemetry")
    series = models.CharField(max_length=80)
    resolution = models.PositiveSmallIntegerField(default=0)
    ts = models.DateTimeField()
    avg = models.FloatField()
    min = models.FloatField()
    max = models.FloatField()
    n = models.PositiveIntegerField(default=1)

    class Meta:
        indexes = [models.Index(fields=["binding", "series", "resolution", "ts"], name="adapter_telemetry_read_idx"),
                   models.Index(fields=["resolution", "ts"], name="adapter_telemetry_sweep_idx")]
        constraints = [models.UniqueConstraint(fields=("binding", "series", "resolution", "ts"),
                                               name="adapter_telemetry_point_once")]


class AdapterTelemetryDrop(models.Model):
    """Decision 328a: telemetry samples NOT stored because the space hit `adapter_telemetry_points`, one row per space per day.

    A cheap counter (never one row per sample) so a limit that drops data is visible: the adapter console, the
    100% notice and the device-adapter-activity report all read it. Operational, bounded to the last 90 days.
    """

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    day = models.DateField()
    count = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("makerspace", "day"), name="adapter_telemetry_drop_day")]


class AdapterConfigVersion(models.Model):
    """A staff-pushed adapter config version; the adapter acknowledges it. Never holds secrets (keys are screened)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="adapter_config_versions")
    version = models.PositiveIntegerField()
    config = models.JSONField(default=dict)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(default=timezone.now)
    ack_outcome = models.CharField(max_length=8, blank=True)
    ack_detail = models.CharField(max_length=200, blank=True)
    acked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-version",)
        constraints = [models.UniqueConstraint(fields=("device", "version"), name="adapter_config_version_once")]


class AdapterAccessCache(models.Model):
    """Status of the offline access cache last issued for a binding. Entries are NOT stored (digests are rebuilt)."""

    binding = models.OneToOneField(AdapterBinding, on_delete=models.CASCADE, primary_key=True,
                                   related_name="access_cache")
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    version = models.PositiveBigIntegerField(default=0)
    entry_count = models.PositiveIntegerField(default=0)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    reconciled_at = models.DateTimeField(null=True, blank=True)
    offline_decisions = models.PositiveIntegerField(default=0)
