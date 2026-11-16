"""A saved "Check shelves" walk (decision 331c): which storage locations staff looked at and what they found.

Staff-only. ``entries`` is a list of ``{"location", "status": "ok"|"attention", "note"}`` rows; the two counts are
denormalised so the history list and the inventory report never have to open the JSON. Append-only in practice:
the service creates rows and never edits them. Like the adapter models it is OMITTED from exports and tenant dumps.
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ShelfCheck(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    checked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    scope_label = models.CharField(max_length=80, blank=True)
    entries = models.JSONField(default=list)
    ok_count = models.PositiveIntegerField(default=0)
    attention_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["makerspace", "-created_at"], name="shelf_check_ms_created_idx")]
