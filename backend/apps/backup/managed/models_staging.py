"""Deployment-local staging lineage; ciphertext bytes live in private storage."""
import uuid

from django.db import models


class ManagedStagedObject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.UUIDField(db_index=True, editable=False)
    label = models.CharField(max_length=80, editable=False)
    attempt = models.UUIDField(default=uuid.uuid4, editable=False)
    identity = models.JSONField(editable=False)
    object_key = models.CharField(max_length=512, unique=True, editable=False)
    size = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    available = models.BooleanField(default=False)
    selected = models.BooleanField(default=False)
    expires_at = models.DateTimeField(db_index=True)
    delete_requested_at = models.DateTimeField(null=True)
    deleted_at = models.DateTimeField(null=True)
    retry_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backup"
        indexes = [models.Index(fields=["owner", "label"], name="managed_stage_owner_label")]
        constraints = [models.UniqueConstraint(fields=["owner", "label"], condition=models.Q(selected=True), name="managed_stage_selected_slot")]


class ManagedPresignLease(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    generation = models.PositiveBigIntegerField(editable=False)
    expires_at = models.DateTimeField(db_index=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backup"
