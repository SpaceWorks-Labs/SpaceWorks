import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


ARCHIVE_PURGE_WARNING = (
    "Downloaded backup archives are outside makerspace purge guarantees. "
    "Delete retained copies separately when they are no longer required."
)


class PlatformBackupSettings(models.Model):
    class Meta:
        # #188: plain-language admin name (the default plural was broken English).
        verbose_name = "backup settings"
        verbose_name_plural = "backup settings"

    automatic_backups_enabled = models.BooleanField(default=False)
    retention_days = models.PositiveSmallIntegerField(
        default=30, validators=(MinValueValidator(1), MaxValueValidator(3650))
    )
    last_scheduled_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)
    # Release 2 L11: a restore drill per space every N days (0 = off), the optional
    # "archive ready" operator notice (off by default, #128 C-24) and a pending
    # re-encryption of archives still encrypted to a retired key (cleared to cancel).
    restore_drill_interval_days = models.PositiveSmallIntegerField(
        default=7, validators=(MaxValueValidator(365),))
    archive_ready_notice_enabled = models.BooleanField(default=False)
    reencrypt_requested_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def load(cls):
        row, _ = cls.objects.get_or_create(pk=1)
        return row

    def __str__(self):
        return "Platform backup settings"


class BackupArchive(models.Model):
    class Scope(models.TextChoices):
        DEPLOYMENT = "deployment", "Full deployment"
        MAKERSPACE = "makerspace", "Makerspace"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        PROMOTING = "promoting", "Promoting"
        AVAILABLE = "available", "Available"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"

    class Trigger(models.TextChoices):
        ON_DEMAND = "on_demand", "Back up now"
        NIGHTLY = "nightly", "Nightly"
        SAFETY = "safety", "Before a restore"
        EXTRACTED = "extracted", "From a whole-platform backup"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scope = models.CharField(max_length=16, choices=Scope.choices)
    # What the payload is: "tenant_slice_v2" (both membership tracks; "tenant_slice_v1" still
    # converts on read) is the per-space raw slice a space restore reads; deployment
    # archives keep their manifest format and leave this blank.
    format = models.CharField(max_length=32, blank=True, default="")
    trigger = models.CharField(max_length=16, choices=Trigger.choices, default=Trigger.ON_DEMAND)
    makerspace = models.ForeignKey(
        "makerspaces.Makerspace", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="backup_archives",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="requested_backup_archives",
    )
    backup_run = models.ForeignKey(
        "backup.BackupRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="archives",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    build_holder = models.UUIDField(null=True, blank=True)
    object_key = models.CharField(max_length=512, unique=True)
    staging_object_key = models.CharField(max_length=512, null=True, blank=True)
    manifest = models.JSONField(default=dict, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    archive_sha256 = models.CharField(max_length=64, blank=True)
    age_encrypted = models.BooleanField(default=False)
    failure_detail = models.CharField(max_length=500, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    download_token_digest = models.CharField(max_length=64, blank=True)
    download_token_expires_at = models.DateTimeField(null=True, blank=True)
    download_token_consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("scope", "makerspace", "status", "created_at"))]
        constraints = [
            models.CheckConstraint(
                condition=(
                    ~models.Q(status="available")
                    | models.Q(expires_at__isnull=False)
                ),
                name="backup_available_requires_expiry",
            ),
        ]


# Stable public model imports; restore and artifact implementations stay split out.
from .models_restore import (  # noqa: E402,F401
    BackupLease,
    DeploymentRecoveryState,
    RestoreOperation,
    RestoreRollbackObject,
)
from .models_artifact_ledger import BackupArtifactComponent, BackupArtifactLedger  # noqa: E402,F401
from .models_runs import BackupRun, BackupRunCoverage  # noqa: E402,F401
from .models_offsite import BackupDestination, BackupDestinationUpload  # noqa: E402,F401
from .models_space_restore import MakerspaceRestoreOperation  # noqa: E402,F401
from .models_keys import BackupKeyFingerprint  # noqa: E402,F401
from .models_drill import RestoreDrillReport  # noqa: E402,F401

from .managed.models import ManagedDeploymentState, ManagedCaptureState, ManagedWriterBoundary  # noqa: F401,E402
from .managed.models_staging import ManagedStagedObject, ManagedPresignLease  # noqa: F401,E402
