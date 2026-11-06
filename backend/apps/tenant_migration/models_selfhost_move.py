"""A Space Manager's request to move their space to a self-hosted server (#128 C-23).

The Space Manager only REQUESTS (with a note) and reads the status; there is no download
surface for them (#111 Q2). The superadmin approves and runs the PORTABLE export from
/control/ with a one-shot recipient key supplied by the target operator plus the platform
key (#111 Q7, #160). The request is platform coordination state: it never travels in an
export, a tenant dump or a per-space backup. ``artifact_path`` is server-local and is
never returned by any API.
"""
from django.utils.translation import gettext_lazy
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class SelfHostMoveRequest(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        EXPORTING = "exporting", "Exporting"
        EXPORTED = "exported", "Exported"
        REJECTED = "rejected", "Rejected"
        FAILED = "failed", gettext_lazy("Export failed")
        CANCELLED = "cancelled", "Cancelled"

    OPEN_STATUSES = ("requested", "approved", "exporting")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="selfhost_move_requests")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.REQUESTED)
    note = models.TextField(max_length=2000, blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="+")
    requested_at = models.DateTimeField(default=timezone.now)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=500, blank=True)
    recipient_fingerprint = models.CharField(max_length=64, blank=True)
    artifact_path = models.CharField(max_length=500, blank=True)
    artifact_sha256 = models.CharField(max_length=64, blank=True)
    exported_at = models.DateTimeField(null=True, blank=True)
    failure_code = models.CharField(max_length=48, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-requested_at",)
        constraints = [models.UniqueConstraint(
            fields=("makerspace",), condition=Q(status__in=("requested", "approved", "exporting")),
            name="tenant_migration_one_open_selfhost_move")]
