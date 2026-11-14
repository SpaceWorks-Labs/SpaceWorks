"""Deployment-local byte debt for uploads that do not yet have an attachment."""
from django.db import models


class StorageQuotaReservation(models.Model):
    # No User FK: this is object-storage coordination, never identity or authority.
    # The presign/attachment's existing audit record attributes the human action.
    # Preserve the source tenant id and exact-key debt after tenant purge. There
    # is deliberately no DB FK/cascade: this deployment-local receipt outlives
    # its parent, just like abandoned-upload reconciliation. Keeping the source
    # id (rather than NULL) also keeps generated RLS scoped after deletion.
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.DO_NOTHING, db_constraint=False)
    object_key = models.CharField(max_length=512, unique=True)
    final_key = models.CharField(max_length=512)
    staging_key = models.CharField(max_length=560)
    bucket = models.CharField(max_length=255)
    final_bucket = models.CharField(max_length=255)
    storage_endpoint = models.CharField(max_length=512, blank=True)
    kind = models.CharField(max_length=20)
    size_bytes = models.PositiveBigIntegerField()
    converted = models.BooleanField(default=False)
    cleaning = models.BooleanField(default=False)
    released = models.BooleanField(default=False)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
