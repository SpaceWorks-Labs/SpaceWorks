"""Restore drill reports (release 2 L11, BK-10/BK-91, #128 C-22).

A drill restores the latest per-space archive into an isolated throwaway database with a
throwaway identity, checks the reconstruction, records this report and destroys both.
The report keeps only counts and a typed outcome: no row data, no key material.
"""
import uuid

from django.db import models
from django.utils import timezone


class RestoreDrillReport(models.Model):
    class Outcome(models.TextChoices):
        PASSED = "passed", "Passed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    makerspace = models.ForeignKey("makerspaces.Makerspace", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    makerspace_id_snapshot = models.PositiveBigIntegerField()
    archive = models.ForeignKey("backup.BackupArchive", null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="+")
    archive_id_snapshot = models.UUIDField()
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    outcome = models.CharField(max_length=16, choices=Outcome.choices)
    error_code = models.CharField(max_length=48, blank=True)
    error_detail = models.CharField(max_length=300, blank=True)
    # {"rows": {label: n}, "row_total": n, "objects_verified": n, "labels": n}
    checks = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-started_at",)
        indexes = [models.Index(fields=("makerspace_id_snapshot", "started_at"), name="backup_drill_space_started")]
