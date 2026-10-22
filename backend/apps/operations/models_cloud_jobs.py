"""Deployment-local scheduler claims; never tenant data or an effect queue."""
import uuid

from django.db import models
from django.utils import timezone


class CloudTaskState(models.Model):
    key = models.CharField(max_length=100, unique=True)
    token = models.UUIDField(null=True, default=None)
    generation = models.PositiveBigIntegerField(default=0)
    status = models.CharField(max_length=16, default="idle", choices=[('idle', 'idle'), ('running', 'running'), ('completed', 'completed'), ('deferred', 'deferred'), ('failed', 'failed'), ('uncertain', 'uncertain'), ('disabled', 'disabled')])
    checkpoint = models.JSONField(default=dict)
    last_attempt_at = models.DateTimeField(null=True)
    heartbeat_at = models.DateTimeField(null=True)
    last_completed_at = models.DateTimeField(null=True)
    next_due_at = models.DateTimeField(null=True, db_index=True)
    failure_code = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(status__in=[
                "idle", "running", "completed", "deferred", "failed", "uncertain", "disabled",
            ]), name="cloud_task_status_valid"),
            models.CheckConstraint(condition=(~models.Q(status__in=["running", "uncertain"]) |
                models.Q(token__isnull=False, last_attempt_at__isnull=False, heartbeat_at__isnull=False)),
                name="cloud_task_claim_complete"),
            models.CheckConstraint(condition=models.Q(generation__gte=0), name="cloud_task_generation_valid"),
        ]
        indexes = [models.Index(fields=["status", "next_due_at"], name="cloud_task_due")]


class CloudTickRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    started_at = models.DateTimeField(default=timezone.now, db_index=True)
    finished_at = models.DateTimeField(null=True, db_index=True)
    duration_ms = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, default="running", choices=[('running', 'running'), ('completed', 'completed'), ('failed', 'failed')])
    completed = models.PositiveIntegerField(default=0)
    deferred = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(status__in=["running", "completed", "failed"]),
                                   name="cloud_tick_status_valid"),
            models.CheckConstraint(condition=(models.Q(status="running", finished_at__isnull=True) |
                models.Q(status__in=["completed", "failed"], finished_at__isnull=False)),
                name="cloud_tick_finish_complete"),
            models.CheckConstraint(condition=(models.Q(finished_at__isnull=True) |
                models.Q(finished_at__gte=models.F("started_at"))), name="cloud_tick_time_order"),
        ]
        indexes = [models.Index(fields=["status", "started_at"], name="cloud_tick_status_start")]


class CloudTickRateWindow(models.Model):
    key = models.CharField(max_length=32, primary_key=True)
    window = models.DateTimeField()
    hits = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(key__in=["ingress", "authenticated"]),
                                   name="cloud_tick_rate_key_valid"),
            models.CheckConstraint(condition=models.Q(hits__gte=0), name="cloud_tick_rate_hits_valid"),
        ]
