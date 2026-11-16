"""A batch run: several queued jobs started together on one machine (#142 OQ-9)."""

from django.conf import settings
from django.db import models


class MachineJobBatch(models.Model):
    """One plate or sheet. Each job keeps its own estimate, planned material and actuals;
    the batch only ties them to one machine run so the machine frees when the last ends."""

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="machine_job_batches")
    machine = models.ForeignKey("machines.Machine", on_delete=models.CASCADE, related_name="job_batches")
    started_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-started_at", "-id"]
        indexes = [models.Index(fields=["machine", "ended_at"], name="job_batch_machine_open_idx")]

    def __str__(self):
        return f"Batch {self.pk} on {self.machine_id}"
