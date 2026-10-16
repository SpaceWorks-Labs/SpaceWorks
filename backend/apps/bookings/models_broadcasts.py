"""Typed resource campaign history over the always-present broadcast engine."""

from django.db import models
from django.db.models import F, Q

from apps.integrations.broadcasts_models import BroadcastCampaign, BroadcastDelivery


class BookingBroadcast(BroadcastCampaign):
    space = models.ForeignKey("bookings.BookableSpace", on_delete=models.CASCADE, related_name="broadcasts")
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    statuses = models.JSONField(default=list)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=Q(window_end__gt=F("window_start")), name="booking_broadcast_window_order",
        )]


class BookingBroadcastDelivery(BroadcastDelivery):
    campaign = models.ForeignKey(BookingBroadcast, on_delete=models.CASCADE, related_name="deliveries")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["campaign", "recipient"], name="uniq_booking_broadcast_account")]
