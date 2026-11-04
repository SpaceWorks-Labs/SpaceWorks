"""Custom check-in lists (X45, lane L21a): swag, lunch, a workshop.

A list is a separate tally beside entry: scanning someone onto it NEVER changes entry
check-in, registration status or evidence. An optional "after entry" rule admits only
people already checked in at the door. A list limited to an L6 add-on admits only buyers
of that add-on on a paid order, each as many times as the quantity they bought. An
archived list is read-only. Online only in v1: there is no offline sync for lists.
"""
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.db.models import Q


class EventCheckInList(models.Model):
    class Kind(models.TextChoices):
        SWAG = "swag", "Swag"
        MEAL = "meal", "Meal"
        WORKSHOP = "workshop", "Workshop"
        OTHER = "other", "Other"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="checkin_lists")
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.OTHER)
    after_entry = models.BooleanField(default=False)
    addon = models.ForeignKey("events.EventAddon", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    per_person = models.PositiveSmallIntegerField(default=1)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["event_id", "pk"]
        constraints = [models.CheckConstraint(condition=Q(per_person__gte=1, per_person__lte=20),
                                              name="event_checkin_list_per_person_bounds")]


class EventCheckInListScan(models.Model):
    """Append-only: one collection on a list."""

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    checkin_list = models.ForeignKey(EventCheckInList, on_delete=models.CASCADE, related_name="scans")
    registration = models.ForeignKey("events.EventRegistration", on_delete=models.CASCADE, related_name="list_scans")
    operation_id = models.UUIDField(default=uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="+")
    scanned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["checkin_list_id", "pk"]
        constraints = [models.UniqueConstraint(fields=["checkin_list", "operation_id"],
                                               name="event_checkin_list_scan_operation")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Check-in list scans are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Check-in list scans are append-only.")
