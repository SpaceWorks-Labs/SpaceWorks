"""One makerspace rolled back to a restore point (owner decisions #110d, #111 Q5/Q15/Q16).

Re-exported from :mod:`apps.backup.models`. Every stage change is audited in the space.
At most one unfinished restore exists per makerspace (database constraint).
"""

from django.utils.translation import gettext_lazy
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class MakerspaceRestoreOperation(models.Model):
    class Stage(models.TextChoices):
        REQUESTED = "requested", "Requested"
        STAGING = "staging", gettext_lazy("Preparing preview")
        PREVIEW_READY = "preview_ready", gettext_lazy("Preview ready")
        APPLYING = "applying", "Restoring"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        ABORTED = "aborted", "Cancelled"

    class Source(models.TextChoices):
        SPACE_ARCHIVE = "space_archive", gettext_lazy("One-space backup")
        DEPLOYMENT_ARCHIVE = "deployment_archive", gettext_lazy("Whole-platform backup")

    TERMINAL = (Stage.COMPLETED, Stage.FAILED, Stage.ABORTED)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    makerspace = models.ForeignKey(
        "makerspaces.Makerspace", on_delete=models.CASCADE, related_name="space_restores",
    )
    archive = models.ForeignKey(
        "backup.BackupArchive", null=True, blank=True, on_delete=models.SET_NULL, related_name="space_restores",
    )
    source = models.CharField(max_length=24, choices=Source.choices, default=Source.SPACE_ARCHIVE)
    safety_archive = models.ForeignKey(
        "backup.BackupArchive", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    stage = models.CharField(max_length=16, choices=Stage.choices, default=Stage.REQUESTED)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    snapshot_at = models.DateTimeField(null=True, blank=True)
    preview = models.JSONField(default=dict, blank=True)
    preview_fingerprint = models.CharField(max_length=64, blank=True)
    progress = models.JSONField(default=dict, blank=True)
    report = models.JSONField(default=dict, blank=True)
    error_code = models.CharField(max_length=48, blank=True)
    error_detail = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    preview_ready_at = models.DateTimeField(null=True, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("makerspace",),
                condition=~Q(stage__in=("completed", "failed", "aborted")),
                name="backup_one_open_space_restore",
            ),
        ]

    @property
    def is_terminal(self):
        return self.stage in self.TERMINAL
