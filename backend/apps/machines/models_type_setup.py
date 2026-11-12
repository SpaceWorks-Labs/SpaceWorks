"""Per-space settings of one machine type that live nowhere else (decision 343 follow-up).

* `MachineTypeSetup` -- booking defaults for the type's bookable machine spaces (applied when one is created,
  and on request to existing ones through the bookings rule service) and the training notes members see on the
  type page, at session start and when asking for a job.
* `MachineTypeDocument` -- files attached to those notes, stored through the machine private-upload path and
  counted against the space's storage.

Notifications are NOT here: per-type notices use the existing recipient routing (rules narrowed by
`RecipientMachineTypeScope`). No user FKs: the audit log records who changed what.
"""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class MachineTypeSetup(models.Model):
    class Approval(models.TextChoices):
        UNSET = "", "Not set"
        INSTANT = "instant", "Instant confirmation"
        APPROVE = "approve", "Staff approval required"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="machine_type_setups")
    machine_type = models.ForeignKey("machines.MachineType", on_delete=models.CASCADE, related_name="space_setups")
    # Null = no default: the bookings app's own default applies.
    booking_slot_minutes = models.PositiveIntegerField(null=True, blank=True,
                                                       validators=[MinValueValidator(1), MaxValueValidator(1440)])
    booking_buffer_before_minutes = models.PositiveIntegerField(null=True, blank=True,
                                                                validators=[MaxValueValidator(1440)])
    booking_buffer_after_minutes = models.PositiveIntegerField(null=True, blank=True,
                                                               validators=[MaxValueValidator(1440)])
    booking_approval_mode = models.CharField(max_length=8, choices=Approval.choices, blank=True, default="")
    training_notes = models.TextField(blank=True)
    notes_at_session_start = models.BooleanField(default=True)
    notes_at_job_request = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["makerspace", "machine_type"],
                                               name="machine_type_setup_unique")]


class MachineTypeDocument(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="machine_type_documents")
    machine_type = models.ForeignKey("machines.MachineType", on_delete=models.CASCADE,
                                     related_name="space_documents")
    title = models.CharField(max_length=200)
    object_key = models.CharField(max_length=255, unique=True)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveBigIntegerField(default=0)
    member_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title", "id"]
