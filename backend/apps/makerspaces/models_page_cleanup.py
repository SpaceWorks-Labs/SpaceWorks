"""Durable byte-cleanup coordination; owner IDs are inert provenance after purge."""

from django.db import models
from django.utils import timezone


class PublicPageObjectCleanup(models.Model):
    owner_kind = models.CharField(max_length=16, choices=(("makerspace", "Makerspace"), ("organization", "Organization")))
    owner_id = models.PositiveBigIntegerField()
    page_id = models.PositiveBigIntegerField()
    object_key = models.CharField(max_length=300, unique=True)
    size_bytes = models.PositiveIntegerField()
    due_at = models.DateTimeField(default=timezone.now, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
