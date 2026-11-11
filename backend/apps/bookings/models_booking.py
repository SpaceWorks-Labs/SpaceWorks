from django.utils.translation import gettext
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from apps.encryption.mappers import ScopedPiiModelMixin

from django.utils import timezone
from .models_spaces import BookableSpace
from .models_arrival import BookingArrivalFields
from .models_departure import BookingDepartureFields


class Booking(ScopedPiiModelMixin, BookingArrivalFields, BookingDepartureFields):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"
        NO_SHOW = "no_show", "No-show"

    space = models.ForeignKey(
        BookableSpace,
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    public_token = models.UUIDField(
        default=uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )
    name = models.TextField()
    email = models.TextField()
    # Optional (#165 auto): the booking form asks for none and a member account may hold none.
    phone = models.TextField(blank=True)
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.CONFIRMED,
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    status_before_cancel = models.CharField(max_length=16, blank=True, default="")
    note = models.TextField(blank=True)
    custom_answers = models.JSONField(null=True, blank=True, default=None)
    # Lane L15 (#159): the quote frozen when a booking awaiting approval was requested;
    # approval charges exactly this. `{}` for instant or legacy bookings. Insert-only.
    pricing_snapshot = models.JSONField(default=dict, blank=True)
    # Decision 216: an authorized replacement of a rejected or cancelled reservation names
    # the original, which keeps its own debt, receipts and history. One replacement each;
    # insert-only (save() below keeps the original value).
    replaces = models.OneToOneField("self", null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="replaced_by", editable=False)
    # Decision 223 (h): a staff-only booking for a space-run event or the space itself: no member
    # booker, never charged, consumes no plan hours. Insert-only (save() keeps the original value).
    is_house = models.BooleanField(default=False, editable=False)
    calendar_sequence = models.PositiveIntegerField(default=0)
    calendar_updated_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")),
                name="booking_end_after_start",
            ),
            models.CheckConstraint(
                condition=Q(is_house=False) | Q(member__isnull=True),
                name="booking_house_has_no_member",
            ),
        ]
        indexes = [
            models.Index(
                fields=["space", "status", "starts_at"],
                name="booking_space_status_idx",
            ),
            models.Index(
                fields=["space", "ends_at"],
                name="booking_space_end_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        from .services_arrival_policy import prepare_booking_save
        prepare_booking_save(self, kwargs)
        self.name = (self.name or "").strip()
        self.email = (self.email or "").strip().lower()
        self.phone = (self.phone or "").strip()
        errors = {
            field: "This field may not be blank."
            for field in ("name", "email")
            if not getattr(self, field)
        }
        if errors:
            raise ValidationError(errors)
        if self.pk:
            original = type(self).objects.only(
                "public_token", "space_id", "pricing_snapshot", "replaces_id", "is_house",
            ).get(pk=self.pk)
            self.public_token = original.public_token
            self.space_id = original.space_id
            self.replaces_id = original.replaces_id
            self.is_house = original.is_house
            if original.pricing_snapshot != self.pricing_snapshot:
                raise ValidationError(gettext("A booking's requested price is frozen."))
        super().save(*args, **kwargs)
