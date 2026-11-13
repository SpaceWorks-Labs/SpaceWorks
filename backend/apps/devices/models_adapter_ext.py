"""Adapter credentials, poses, access decisions, usage and watch sessions (decision 312).

Credentials are digests only. Poses are device-specific coordinates and staff-only. The access log and the
usage log are append-only evidence. All of it is OMITTED from exports and tenant dumps (device-bound).
"""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_noop

from .models_adapter import AdapterBinding


class AdapterCredential(models.Model):
    """A member's NFC tag or PIN for adapter access. Only an HMAC digest is stored, never the secret."""

    class Kind(models.TextChoices):
        NFC = "nfc", "NFC"
        PIN = "pin", "PIN"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="adapter_credentials")
    kind = models.CharField(max_length=8, choices=Kind.choices)
    digest = models.CharField(max_length=64)
    label = models.CharField(max_length=60, blank=True)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    disabled_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("makerspace", "kind", "digest"), name="adapter_credential_digest_once"),
            models.UniqueConstraint(fields=("makerspace", "user", "kind"), condition=Q(disabled_at__isnull=True),
                                    name="adapter_credential_one_live_per_kind"),
        ]


class AdapterPose(models.Model):
    """A saved pointer pose for one target of a shelf-pointer binding. Staff-only; never on a public surface."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    binding = models.ForeignKey(AdapterBinding, on_delete=models.CASCADE, related_name="poses")
    target_type = models.CharField(max_length=24)
    target_id = models.CharField(max_length=64)
    pose = models.JSONField(default=dict)
    note = models.CharField(max_length=80, blank=True)
    saved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="+")
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("binding", "target_type", "target_id"),
                                               name="adapter_pose_once")]


class AdapterAccessLog(models.Model):
    """Append-only: one row per access decision (grant or deny) with its reason code."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="adapter_access_logs")
    binding = models.ForeignKey(AdapterBinding, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    member = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="+")
    credential_type = models.CharField(max_length=8)
    allowed = models.BooleanField()
    reason = models.CharField(max_length=48)
    session_id_snapshot = models.PositiveBigIntegerField(null=True, blank=True)
    # Decision 321: a decision the adapter made OFFLINE from its signed cache, reconciled on reconnect.
    offline = models.BooleanField(default=False)
    operation_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["device", "created_at"], name="adapter_access_device_idx")]
        constraints = [models.UniqueConstraint(fields=("device", "operation_id"), condition=Q(operation_id__isnull=False),
                                               name="adapter_access_offline_once")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("AdapterAccessLog rows are append-only.")
        return super().save(*args, **kwargs)


class AdapterUsageLog(models.Model):
    """Append-only usage record an adapter reported for one session or job; idempotent by operation id."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="adapter_usage_logs")
    binding = models.ForeignKey(AdapterBinding, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    operation_id = models.UUIDField()
    session_id_snapshot = models.PositiveBigIntegerField(null=True, blank=True)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    active_minutes = models.PositiveIntegerField(default=0)
    idle_minutes = models.PositiveIntegerField(default=0)
    outcome = models.CharField(max_length=12)
    error_code = models.CharField(max_length=48, blank=True)
    consumptions = models.JSONField(default=list)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-created_at",)
        constraints = [models.UniqueConstraint(fields=("device", "operation_id"), name="adapter_usage_once")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("AdapterUsageLog rows are append-only.")
        return super().save(*args, **kwargs)


class AdapterWatch(models.Model):
    """A short-lived, audited camera watch session; signaling is relayed here, media never touches the server."""

    class Status(models.TextChoices):
        ACTIVE = "active", gettext_noop("Active")
        ENDED = "ended", gettext_noop("Ended")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    binding = models.ForeignKey(AdapterBinding, on_delete=models.CASCADE, related_name="watches")
    viewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="+")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE)
    signals = models.JSONField(default=list)  # bounded list of {from: viewer|adapter, kind, payload}
    # Opt-in recording (decision 312 addendum): the adapter uploads one clip through a presigned PUT; it is
    # retention-limited (swept by a Celery task) and every step is audited. Off unless the watch asked for it.
    record = models.BooleanField(default=False)
    # Decision 321: audio track (receive-only), staff push-to-talk, and the audio-recording notice acknowledgement.
    audio = models.BooleanField(default=False)
    talk = models.BooleanField(default=False)
    audio_notice_ack = models.BooleanField(default=False)
    talk_presses = models.PositiveSmallIntegerField(default=0)
    recording_key = models.CharField(max_length=200, blank=True)
    recording_expires_at = models.DateTimeField(null=True, blank=True)
    recording_purged_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
