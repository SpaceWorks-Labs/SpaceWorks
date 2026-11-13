"""The uniform job flow's columns on `MachineServiceRequest` (#140-#142).

An abstract mixin so the request model keeps one table and one transition authority
(`service_workflow*`) while its file stays under the size ceiling. Every field is
nullable or defaulted, so rows from before the flow read as "nothing asked yet".
"""

from django.db import models


class JobFlowFields(models.Model):
    # Queue order (OQ-5/OQ-6): one sort key shared by the position, the ETA simulator,
    # the "You're next" notice and the staff board -- urgent first, then the anchor.
    # Empty means "the submission time"; it is set only when the place moves.
    queued_at = models.DateTimeField(null=True, blank=True, db_index=True)
    urgent = models.BooleanField(default=False)
    urgent_reason = models.CharField(max_length=200, blank=True)
    needed_by = models.DateField(null=True, blank=True)
    preassigned_machine = models.ForeignKey(
        "machines.Machine", null=True, blank=True, on_delete=models.SET_NULL, related_name="preassigned_jobs")
    batch = models.ForeignKey(
        "machines.MachineJobBatch", null=True, blank=True, on_delete=models.SET_NULL, related_name="jobs")
    # Intake (#140): copies, the member's own material, and their slicer estimate (a hint).
    copies = models.PositiveSmallIntegerField(default=1)
    own_material = models.BooleanField(default=False)
    material_note = models.CharField(max_length=200, blank=True)
    member_estimate_minutes = models.PositiveIntegerField(null=True, blank=True)
    # Needs changes (OQ-14): one staff message per request, plus the member's answer.
    changes_requested_at = models.DateTimeField(null=True, blank=True)
    changes_code = models.CharField(max_length=32, blank=True)
    changes_message = models.TextField(blank=True)
    member_note = models.TextField(blank=True)
    reject_code = models.CharField(max_length=32, blank=True)
    # Quote (OQ-2/OQ-3/OQ-4): the frozen L15 quote, its validity and the answer.
    quote_snapshot = models.JSONField(null=True, blank=True)
    quote_digest = models.CharField(max_length=64, blank=True)
    quoted_at = models.DateTimeField(null=True, blank=True)
    quote_expires_at = models.DateTimeField(null=True, blank=True)
    quote_reminded_at = models.DateTimeField(null=True, blank=True)
    quote_approved_at = models.DateTimeField(null=True, blank=True)
    prepay = models.BooleanField(default=False)
    # Failure (OQ-8): reason code, whose fault, and what happened next.
    fail_code = models.CharField(max_length=32, blank=True)
    fail_fault = models.CharField(max_length=8, blank=True)
    failure_outcome = models.CharField(max_length=16, blank=True)
    auto_requeue_count = models.PositiveSmallIntegerField(default=0)
    # Pickup (OQ-7/OQ-15): the code anyone collecting must show, where it waits, reminders.
    pickup_code = models.CharField(max_length=8, blank=True, db_index=True)
    pickup_location = models.CharField(max_length=120, blank=True)
    pickup_reminders_sent = models.PositiveSmallIntegerField(default=0)
    uncollected_at = models.DateTimeField(null=True, blank=True)
    # Whoever showed the pickup code: personal data, encrypted like the requester's name.
    collected_by_name = models.TextField(blank=True)

    class Meta:
        abstract = True
