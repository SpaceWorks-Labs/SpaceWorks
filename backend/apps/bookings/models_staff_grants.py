"""Deployment-local typed resource credentials; omitted from portable archives."""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.makerspaces.resource_grants_models import ResourceStaffGrant, ResourceStaffGrantInvite
from .booking_permissions import PERMISSIONS, validate_permissions


class _BookingSpaceScope(models.Model):
    space = models.ForeignKey("bookings.BookableSpace", on_delete=models.CASCADE, related_name="%(class)s_rows")
    permissions = models.JSONField(validators=[validate_permissions])
    permission_vocabulary = PERMISSIONS

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.space.makerspace_id != self.makerspace_id:
            raise ValidationError("The resource must belong to this makerspace.")


class BookingSpaceStaffGrant(_BookingSpaceScope, ResourceStaffGrant):
    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["user", "space"], condition=Q(revoked_at__isnull=True),
            name="booking_staff_grant_active_space",
        )]


class BookingSpaceStaffGrantInvite(_BookingSpaceScope, ResourceStaffGrantInvite):
    pass
