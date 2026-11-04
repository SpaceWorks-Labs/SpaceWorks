"""Durable byte-cleanup coordination; owner IDs are inert provenance after purge."""

from django.db import models
from django.utils import timezone


class PublicPageObjectCleanup(models.Model):
    owner_kind = models.CharField(max_length=16, choices=(("makerspace", "Makerspace"),
        ("organization", "Organization"), ("event", "Event website")))
    owner_id = models.PositiveBigIntegerField()
    page_id = models.PositiveBigIntegerField()
    object_key = models.CharField(max_length=300, unique=True)
    size_bytes = models.PositiveIntegerField()
    # False survives a clone rollback: these orphan bytes remain quota debt until
    # deletion, but must not be subtracted from the rolled-back tenant counter.
    storage_accounted = models.BooleanField(default=True)
    # Persist the checked import/key ownership proof before owner deletion can
    # remove the import journal which originally proved a collision-safe key.
    ownership_proven = models.BooleanField(default=False)
    due_at = models.DateTimeField(default=timezone.now, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=("owner_kind", "owner_id", "storage_accounted", "completed_at"),
                                name="page_cleanup_owner_debt")]
