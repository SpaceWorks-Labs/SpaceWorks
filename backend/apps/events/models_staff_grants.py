"""Revocable event credentials. These rows never travel in portable archives."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.makerspaces.resource_grants_models import ResourceStaffGrant, ResourceStaffGrantInvite

from .event_permissions import PERMISSIONS, validate_permissions


class _EventStaffScope(models.Model):
    event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.CASCADE, related_name="%(class)s_rows")
    series = models.ForeignKey("events.EventSeries", null=True, blank=True, on_delete=models.CASCADE, related_name="%(class)s_rows")
    permissions = models.JSONField(validators=[validate_permissions])
    permission_vocabulary = PERMISSIONS

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        validate_permissions(self.permissions)
        if bool(self.event_id) == bool(self.series_id):
            raise ValidationError("Choose exactly one event or series.")
        target = self.event if self.event_id else self.series
        if target.makerspace_id != self.makerspace_id:
            raise ValidationError("The event or series must belong to this makerspace.")


class EventStaffGrant(_EventStaffScope, ResourceStaffGrant):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_staff_grants")

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(Q(event__isnull=False, series__isnull=True) | Q(event__isnull=True, series__isnull=False)), name="event_staff_grant_one_target"),
            models.UniqueConstraint(fields=["user", "event"], condition=Q(revoked_at__isnull=True), name="event_staff_grant_active_event"),
            models.UniqueConstraint(fields=["user", "series"], condition=Q(revoked_at__isnull=True), name="event_staff_grant_active_series"),
        ]


class EventStaffGrantInvite(_EventStaffScope, ResourceStaffGrantInvite):
    class Meta:
        constraints = [
            models.CheckConstraint(condition=(Q(event__isnull=False, series__isnull=True) | Q(event__isnull=True, series__isnull=False)), name="event_staff_invite_one_target"),
        ]
