"""Venue fees for hosting (release 2 L6, #128 C-20, Q-V1 (a)).

The space charges an OUTSIDE organiser for holding their event at the venue: a member
running their own event, or a co-hosting organisation through its named contact. The
fee resolves through `pricing.quote("events", ...)`: this row's own Free/Custom amount,
else the room's price override, else the space default (flat and/or per hour). It is
charged once, when the event is confirmed (published), as one `Payment` with subject
`event_venue_fee` recorded as events income. Waivers and refunds are staff decisions.
"""

from django.utils.translation import gettext_noop
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from apps.payments.money_model import MoneyDecimalField


class EventVenueFee(models.Model):
    class Mode(models.TextChoices):
        INHERIT = "inherit", gettext_noop("Use the room or space price")
        FREE = "free", "Free"
        CUSTOM = "custom", gettext_noop("Custom price")

    class Basis(models.TextChoices):
        FLAT = "flat", gettext_noop("Flat fee")
        PER_HOUR = "per_hour", gettext_noop("Per hour")

    class Status(models.TextChoices):
        CONFIGURED = "configured", gettext_noop("Not charged yet")
        CHARGED = "charged", "Charged"
        FREE = "free", gettext_noop("Nothing to charge")

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    event = models.OneToOneField("events.Event", on_delete=models.CASCADE, related_name="venue_fee")
    #: Who pays: always a person's account (a member organiser or an organisation's contact).
    payer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="event_venue_fees")
    organization = models.ForeignKey("organizations.Organization", null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="+")
    room = models.ForeignKey("bookings.BookableSpace", null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="+")
    mode = models.CharField(max_length=8, choices=Mode.choices, default=Mode.INHERIT)
    basis = models.CharField(max_length=8, choices=Basis.choices, default=Basis.FLAT)
    amount = MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True,
                                 validators=[MinValueValidator(0)])
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CONFIGURED)
    charged_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(Q(mode="custom", amount__isnull=False, amount__gte=0)
                                              | (~Q(mode="custom") & Q(amount__isnull=True))),
                                   name="event_venue_fee_amount_matches_mode"),
        ]
