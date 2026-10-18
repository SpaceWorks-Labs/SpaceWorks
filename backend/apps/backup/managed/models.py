"""Integrator imports these models into backup.models and authors the migration.

These deployment-local coordination records must be omitted from portable dumps,
tenant archives and restored deployment state. They are never tenant data.
"""

import uuid

from django.db import models


class ManagedDeploymentState(models.Model):
    deployment_id = models.UUIDField(editable=False, unique=True)
    database_uuid = models.UUIDField(editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backup"
        constraints = [models.CheckConstraint(condition=models.Q(pk=1), name="managed_deployment_singleton")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Managed deployment binding is immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Managed deployment binding cannot be deleted.")


class ManagedCaptureState(models.Model):
    generation = models.PositiveBigIntegerField(default=1)
    paused_by = models.UUIDField(null=True, editable=False)
    paused_at = models.DateTimeField(null=True, editable=False)
    drain_until = models.DateTimeField(null=True, editable=False)

    class Meta:
        app_label = "backup"
        constraints = [
            models.CheckConstraint(condition=models.Q(pk=1), name="managed_capture_singleton"),
            models.CheckConstraint(condition=models.Q(generation__gte=1), name="managed_capture_generation_positive"),
            models.CheckConstraint(
                condition=(models.Q(paused_by__isnull=True, paused_at__isnull=True, drain_until__isnull=True)
                           | models.Q(paused_by__isnull=False, paused_at__isnull=False, drain_until__isnull=False)),
                name="managed_capture_pause_complete",
            ),
        ]


class ManagedWriterBoundary(models.Model):
    """An active/uncertain boundary never disappears merely because its lease aged."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    generation = models.PositiveBigIntegerField(editable=False, db_index=True)
    category = models.CharField(max_length=24, editable=False)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, editable=False)
    uncertain = models.BooleanField(default=False)

    class Meta:
        app_label = "backup"
        indexes = [models.Index(fields=["finished_at", "generation"], name="managed_writer_active")]
