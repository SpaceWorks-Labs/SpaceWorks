"""Ordered public place photos for a bookable space.

Bytes live in the PUBLIC image bucket under the space's own prefix
(`spaces/<makerspace>/<space>/images/`), reached only through the staging-key
presign -> finalize flow, so the final key is never client-writable. Each row
carries its charged size so a delete releases exactly what the upload charged.
"""

from django.conf import settings
from django.db import models

MAX_PHOTOS_PER_SPACE = 12


class BookableSpacePhoto(models.Model):
    space = models.ForeignKey("bookings.BookableSpace", on_delete=models.CASCADE,
                              related_name="photos")
    object_key = models.CharField(max_length=500, unique=True)
    size_bytes = models.PositiveIntegerField()
    caption = models.CharField(max_length=200, blank=True, default="")
    position = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("position", "id")
        indexes = [models.Index(fields=["space", "position"], name="bookspace_photo_order_idx")]

    @property
    def makerspace_id(self):
        return self.space.makerspace_id
