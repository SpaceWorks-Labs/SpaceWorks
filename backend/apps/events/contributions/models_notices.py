from django.db import models
from django.db.models import Q
from .models_base import EventBound


class EventContributorNotice(EventBound):
    signup = models.ForeignKey("events.EventShiftSignup", null=True, blank=True, on_delete=models.CASCADE)
    booking = models.ForeignKey("events.OfficeHoursBooking", null=True, blank=True, on_delete=models.CASCADE)
    kind = models.CharField(max_length=24)
    generation = models.PositiveIntegerField()
    available_at = models.DateTimeField()
    delivered_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    claim_uuid = models.UUIDField(null=True, blank=True)
    claim_until = models.DateTimeField(null=True, blank=True)

    class Meta(EventBound.Meta):
        constraints = [
            models.CheckConstraint(condition=(Q(signup__isnull=False, booking__isnull=True)
                | Q(signup__isnull=True, booking__isnull=False)), name="event_contributor_notice_subject"),
            models.UniqueConstraint(fields=["signup", "kind", "generation"], name="event_signup_notice_generation"),
            models.UniqueConstraint(fields=["booking", "kind", "generation"], name="event_booking_notice_generation"),
        ]
