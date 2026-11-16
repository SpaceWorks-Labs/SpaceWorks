"""Revocable event credentials. These rows never travel in portable archives."""

from django.utils.translation import gettext
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.makerspaces.resource_grants_models import ResourceStaffGrant, ResourceStaffGrantInvite

from .event_permissions import PERMISSIONS, validate_permissions


class RoleLabel(models.TextChoices):
    """Display-only name for what a delegated person does at the event.

    It never widens or narrows authority -- ``permissions`` alone decides that. It exists
    so the Team tab can say "Speaker" instead of listing raw permission keys, and so a
    later contribution history can tell speakers from door volunteers.
    """

    SPEAKER = "speaker", "Speaker"
    VOLUNTEER = "volunteer", "Volunteer"
    CHECK_IN = "check_in", "Check-in"


class _EventStaffScope(models.Model):
    event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.CASCADE, related_name="%(class)s_rows")
    series = models.ForeignKey("events.EventSeries", null=True, blank=True, on_delete=models.CASCADE, related_name="%(class)s_rows")
    permissions = models.JSONField(validators=[validate_permissions])
    role_label = models.CharField(max_length=16, choices=RoleLabel.choices, blank=True, default="")
    permission_vocabulary = PERMISSIONS

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        validate_permissions(self.permissions)
        if bool(self.event_id) == bool(self.series_id):
            raise ValidationError(gettext("Choose exactly one event or series."))
        target = self.event if self.event_id else self.series
        if target.makerspace_id != self.makerspace_id:
            raise ValidationError(gettext("The event or series must belong to this makerspace."))


class EventStaffGrant(_EventStaffScope, ResourceStaffGrant):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_staff_grants")

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(Q(event__isnull=False, series__isnull=True) | Q(event__isnull=True, series__isnull=False)), name="event_staff_grant_one_target"),
            models.UniqueConstraint(fields=["user", "event"], condition=Q(revoked_at__isnull=True), name="event_staff_grant_active_event"),
            models.UniqueConstraint(fields=["user", "series"], condition=Q(revoked_at__isnull=True), name="event_staff_grant_active_series"),
        ]


class EventStaffGrantInvite(_EventStaffScope, ResourceStaffGrantInvite):
    # Decision 221(i): a limited co-organizer's invite carries the same track/window limit, and
    # redemption writes a manual entitlement with it. Empty/None means unlimited (managers only).
    track_ids = models.JSONField(default=list, blank=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(Q(event__isnull=False, series__isnull=True) | Q(event__isnull=True, series__isnull=False)), name="event_staff_invite_one_target"),
        ]
