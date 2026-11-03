"""Ticket orders (release 2 L6, G27): one buyer, several seats, one `Payment`.

An order is money and seats, never admission: every seat becomes ONE registration for
ONE attendee account, created through the ordinary registration service when the buyer
pays (their own seat) or when the attendee signs in and claims it. No seat is ever a
registration without an account (Hard Rule, #71). The order's `Payment` (subject
`event_order`) carries the whole amount; the seats' registrations carry no charge of
their own. `EventOrderLine.unit_amount` is the frozen per-ticket price L24 reads.
"""

import secrets

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.encryption.mappers import ScopedPiiModelMixin

MONEY = {"max_digits": 12, "decimal_places": 2}


class EventSalesSettings(models.Model):
    """Per-event selling rules: booking fee, order size, transfers, the refund override."""

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    event = models.OneToOneField("events.Event", on_delete=models.CASCADE, related_name="sales_settings")
    booking_fee_fixed = models.DecimalField(**MONEY, default=0, validators=[MinValueValidator(0)])
    booking_fee_bps = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(10000)])
    max_tickets_per_order = models.PositiveSmallIntegerField(default=10, validators=[MinValueValidator(1)])
    transfers_allowed = models.BooleanField(default=False)
    type_changes_allowed = models.BooleanField(default=False)
    #: Transfers and type changes close this many hours before the start.
    transfer_cutoff_hours = models.PositiveIntegerField(default=0)
    # G34: this event's own refund policy. After the first sale it may only become more
    # generous (`cancellation_policy.require_more_generous`).
    refund_override = models.BooleanField(default=False)
    full_before_minutes = models.PositiveIntegerField(default=0)
    partial_before_minutes = models.PositiveIntegerField(default=0)
    partial_percent = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    cancellation_fee = models.DecimalField(**MONEY, default=0, validators=[MinValueValidator(0)])
    #: Staff-authored, shown to buyers before payment. Never personal data.
    policy_text = models.TextField(blank=True, default="", max_length=2000)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(full_before_minutes__gte=models.F("partial_before_minutes")),
                                   name="event_sales_refund_windows_ordered"),
            models.CheckConstraint(condition=Q(partial_percent__lte=100, booking_fee_bps__lte=10000,
                                               booking_fee_fixed__gte=0, cancellation_fee__gte=0),
                                   name="event_sales_amounts_valid"),
        ]


class EventOrder(models.Model):
    class Kind(models.TextChoices):
        TICKETS = "tickets", "Tickets"
        PASS = "pass", "Series pass"
        TYPE_CHANGE = "type_change", "Ticket type change"

    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting payment"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Checkout expired"
        #: Paid without a held seat and the event filled first; a staff-approved refund is due.
        UNFULFILLED = "unfulfilled", "Could not be seated"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.CASCADE, related_name="orders")
    series = models.ForeignKey("events.EventSeries", null=True, blank=True, on_delete=models.CASCADE,
                               related_name="orders")
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="event_orders")
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.TICKETS)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    currency = models.CharField(max_length=3)
    subtotal = models.DecimalField(**MONEY, default=0)
    discount_total = models.DecimalField(**MONEY, default=0)
    fee_total = models.DecimalField(**MONEY, default=0)
    total = models.DecimalField(**MONEY, default=0)
    #: The frozen order quote (lines, promo, fee, digest). Insert-only, like `Payment.pricing_snapshot`.
    pricing_snapshot = models.JSONField(default=dict, blank=True)
    digest = models.CharField(max_length=64, blank=True, default="")
    promo_code = models.ForeignKey("events.EventPromoCode", null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="orders")
    #: Type changes: the registration whose ticket type this order pays the difference for.
    source_registration = models.ForeignKey("events.EventRegistration", null=True, blank=True,
                                            on_delete=models.SET_NULL, related_name="type_change_orders")
    target_ticket_type = models.ForeignKey("events.EventTicketType", null=True, blank=True,
                                           on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    reminded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["makerspace", "status", "created_at"], name="event_order_status_idx")]
        constraints = [
            models.CheckConstraint(condition=(Q(event__isnull=False, series__isnull=True)
                                              | Q(event__isnull=True, series__isnull=False)),
                                   name="event_order_one_owner"),
            models.CheckConstraint(condition=Q(subtotal__gte=0, discount_total__gte=0, fee_total__gte=0, total__gte=0),
                                   name="event_order_amounts_nonnegative"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            frozen = type(self).objects.filter(pk=self.pk).values_list("pricing_snapshot", "total").first()
            if frozen and (frozen[0] != self.pricing_snapshot or frozen[1] != self.total):
                from django.core.exceptions import ValidationError
                raise ValidationError("An order's quote is frozen once placed.")
        return super().save(*args, **kwargs)


class EventOrderLine(models.Model):
    class Kind(models.TextChoices):
        TICKET = "ticket", "Ticket"
        ADDON = "addon", "Add-on"
        PASS = "pass", "Series pass"
        TYPE_CHANGE = "type_change", "Type change difference"

    order = models.ForeignKey(EventOrder, on_delete=models.CASCADE, related_name="lines")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    ticket_type = models.ForeignKey("events.EventTicketType", null=True, blank=True, on_delete=models.PROTECT,
                                    related_name="order_lines")
    addon = models.ForeignKey("events.EventAddon", null=True, blank=True, on_delete=models.PROTECT,
                              related_name="order_lines")
    variant = models.ForeignKey("events.EventAddonVariant", null=True, blank=True, on_delete=models.PROTECT,
                                related_name="order_lines")
    pass_type = models.ForeignKey("events.EventPassType", null=True, blank=True, on_delete=models.PROTECT,
                                  related_name="order_lines")
    label = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    seats_per_unit = models.PositiveSmallIntegerField(default=0)
    #: Frozen per-unit price (the pay-what-you-want amount chosen, for PWYW tickets).
    unit_amount = models.DecimalField(**MONEY)
    discount_amount = models.DecimalField(**MONEY, default=0)
    line_total = models.DecimalField(**MONEY)

    class Meta:
        ordering = ["order_id", "pk"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1, unit_amount__gte=0, discount_amount__gte=0,
                                               line_total__gte=0), name="event_order_line_amounts"),
        ]


class EventOrderSeat(ScopedPiiModelMixin, models.Model):
    """One admission. The buyer's own seat, or a seat held for an attendee's email."""

    class Status(models.TextChoices):
        UNCLAIMED = "unclaimed", "Waiting for the attendee"
        CLAIMED = "claimed", "Claimed"
        VOID = "void", "Void"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    order = models.ForeignKey(EventOrder, on_delete=models.CASCADE, related_name="seats")
    line = models.ForeignKey(EventOrderLine, on_delete=models.CASCADE, related_name="seats")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="order_seats")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.UNCLAIMED)
    attendee_email = models.TextField(blank=True, default="")
    #: SHA-256 of the emailed claim token. The default is a random value nobody holds, so
    #: a seat is claimable only after an invite mints a token (and a moved space re-sends).
    claim_token_digest = models.CharField(max_length=64, unique=True, default=secrets.token_hex, editable=False)
    registration = models.OneToOneField("events.EventRegistration", null=True, blank=True,
                                        on_delete=models.SET_NULL, related_name="order_seat")
    created_at = models.DateTimeField(auto_now_add=True)
    invited_at = models.DateTimeField(null=True, blank=True)
    reminded_at = models.DateTimeField(null=True, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["order_id", "pk"]
        indexes = [models.Index(fields=["event", "status"], name="event_order_seat_status_idx")]
        constraints = [
            models.CheckConstraint(condition=~Q(status="claimed") | Q(claimed_at__isnull=False),
                                   name="event_order_seat_claimed_at"),
        ]


class EventOrderDue(models.Model):
    """An amount the space owes back on an order: append-only, staff approve the refund case."""

    class Kind(models.TextChoices):
        SEAT_CANCELLED = "seat_cancelled", "A seat was cancelled"
        EVENT_CANCELLED = "event_cancelled", "The event was cancelled"
        OCCURRENCE_CANCELLED = "occurrence_cancelled", "A pass occurrence was cancelled"
        TYPE_CHANGE = "type_change", "Changed to a cheaper ticket"
        UNFULFILLED = "unfulfilled", "No seat was left"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    order = models.ForeignKey(EventOrder, on_delete=models.CASCADE, related_name="dues")
    kind = models.CharField(max_length=24, choices=Kind.choices)
    event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    seat = models.ForeignKey(EventOrderSeat, null=True, blank=True, on_delete=models.SET_NULL, related_name="dues")
    amount = models.DecimalField(**MONEY)
    refund_case = models.ForeignKey("payments.RefundCase", null=True, blank=True, on_delete=models.PROTECT,
                                    related_name="event_order_dues")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order_id", "pk"]
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="event_order_due_positive")]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValueError("Order dues are append-only.")
        return super().save(*args, **kwargs)
