"""Shop orders (release 2 L22): one buyer, several lines, ONE `Payment` (subject `shop_order`).

An online order is placed from the public shop page by a signed-in person or a guest who
confirmed their email with a code (Q-S5); a front-desk sale is an order on the `pos`
channel, paid and handed over at once. The quote the buyer was shown is frozen on the
order (and on its `Payment`), so preview = charge (L15). Pickup only, at the space or at
one of its events (Q-S3, #135); no shipping. Every refund is a staff-approved refund case
(#59); a returned line goes back to stock or is written off (`ShopOrderReturn`).
"""

from django.utils.translation import gettext, gettext_noop
import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.encryption.mappers import ScopedPiiModelMixin

MONEY = {"max_digits": 12, "decimal_places": 2}


def new_status_secret():
    return secrets.token_hex(16)


class ShopOrder(ScopedPiiModelMixin, models.Model):
    class Channel(models.TextChoices):
        ONLINE = "online", "Online"
        POS = "pos", gettext_noop("Front desk")

    class Status(models.TextChoices):
        HELD = "held", gettext_noop("Checkout in progress")
        AWAITING_PAYMENT = "awaiting_payment", gettext_noop("Pay at the desk")
        PAID = "paid", "Paid"
        READY = "ready", gettext_noop("Ready for pickup")
        COLLECTED = "collected", "Collected"
        CANCELLED = "cancelled", "Cancelled"
        #: Paid without held stock and the stock ran out first; a staff-approved refund is due.
        UNFULFILLED = "unfulfilled", gettext_noop("Paid, out of stock")
        REFUNDED = "refunded", "Refunded"

    class Pickup(models.TextChoices):
        SPACE = "space", gettext_noop("At the space")
        EVENT = "event", gettext_noop("At an event")

    OPEN_STATUSES = (Status.HELD, Status.AWAITING_PAYMENT)
    PAID_STATUSES = (Status.PAID, Status.READY)

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="shop_orders")
    channel = models.CharField(max_length=8, choices=Channel.choices, default=Channel.ONLINE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.HELD)
    #: The signed-in buyer, or NULL for a guest (name + confirmed email) or an anonymous desk sale.
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                              related_name="shop_orders")
    #: Scoped PII (encrypted at rest, `encryption/registry_r2_l22`).
    guest_name = models.TextField(blank=True, default="")
    guest_email = models.TextField(blank=True, default="")
    pickup_at = models.CharField(max_length=8, choices=Pickup.choices, default=Pickup.SPACE)
    pickup_event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="shop_pickups")
    #: Shown to the buyer and typed at the desk to collect. Unique per space.
    pickup_code = models.CharField(max_length=12)
    currency = models.CharField(max_length=3)
    subtotal = models.DecimalField(**MONEY, default=0)
    discount_total = models.DecimalField(**MONEY, default=0)
    #: The frozen quote total (tax-inclusive with `shop.tax` on).
    total = models.DecimalField(**MONEY, default=0)
    tax_total = models.DecimalField(**MONEY, default=0)
    #: What the buyer owes: the charge's amount (the total plus any exclusive tax on top).
    amount_due = models.DecimalField(**MONEY, default=0)
    #: The frozen quote (lines, discount, digest). Insert-only, like `Payment.pricing_snapshot`.
    pricing_snapshot = models.JSONField(default=dict, blank=True)
    digest = models.CharField(max_length=64, blank=True, default="")
    #: Bearer secret of the guest's signed status link; never exported (a moved space re-sends).
    status_secret = models.CharField(max_length=32, default=new_status_secret, editable=False, unique=True)
    cash_session = models.ForeignKey("shop.ShopCashSession", null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="orders")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    #: An unpaid online order lapses at this time (its stock hold, when there is one, too).
    expires_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    collected_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                                     related_name="+")
    closed_at = models.DateTimeField(null=True, blank=True)
    close_reason = models.CharField(max_length=24, blank=True, default="")
    #: Q-S17: how many uncollected reminders went out (0, 1 or 2).
    reminders_sent = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["makerspace", "status", "created_at"], name="shop_order_status_idx")]
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "pickup_code"], name="shop_order_unique_pickup_code"),
            models.CheckConstraint(condition=Q(subtotal__gte=0, discount_total__gte=0, total__gte=0, tax_total__gte=0,
                                               amount_due__gte=0), name="shop_order_amounts_nonnegative"),
            models.CheckConstraint(condition=Q(pickup_at="space") | Q(channel="online"),
                                   name="shop_order_desk_sale_at_space"),
            models.CheckConstraint(condition=~Q(status="collected") | Q(collected_at__isnull=False),
                                   name="shop_order_collected_at"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            frozen = type(self).objects.filter(pk=self.pk).values_list("pricing_snapshot", "total").first()
            if frozen and (frozen[0] != self.pricing_snapshot or frozen[1] != self.total):
                raise ValidationError(gettext("An order's quote is frozen once placed."))
        return super().save(*args, **kwargs)

    @property
    def is_guest(self):
        return self.buyer_id is None


class ShopOrderLine(models.Model):
    order = models.ForeignKey(ShopOrder, on_delete=models.CASCADE, related_name="lines")
    variant = models.ForeignKey("shop.ShopVariant", on_delete=models.PROTECT, related_name="order_lines")
    label = models.CharField(max_length=240)
    sku = models.CharField(max_length=64, blank=True, default="")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    #: Frozen per-unit price, the discount on the line and the line's net amount.
    unit_amount = models.DecimalField(**MONEY)
    discount_amount = models.DecimalField(**MONEY, default=0)
    line_total = models.DecimalField(**MONEY)
    #: Q-S2 (with `shop.tax` on): the tax class used and the line's inclusive split.
    tax_rate_bps = models.PositiveIntegerField(null=True, blank=True)
    hsn_code = models.CharField(max_length=8, blank=True, default="")
    taxable_amount = models.DecimalField(**MONEY, default=0)
    tax_amount = models.DecimalField(**MONEY, default=0)

    class Meta:
        ordering = ["order_id", "pk"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1, unit_amount__gte=0, discount_amount__gte=0,
                                               line_total__gte=0), name="shop_order_line_amounts"),
        ]


class ShopOrderReturn(models.Model):
    """Units of one line taken back (Q-S7): restocked or written off, and the refund owed.

    Append-only. The goods move when staff record the return; the money moves only when
    staff approve the refund case it opened (#59).
    """

    class Disposition(models.TextChoices):
        RESTOCK = "restock", gettext_noop("Back to stock")
        WRITE_OFF = "write_off", gettext_noop("Written off")

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    order = models.ForeignKey(ShopOrder, on_delete=models.CASCADE, related_name="returns")
    line = models.ForeignKey(ShopOrderLine, on_delete=models.CASCADE, related_name="returns")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    disposition = models.CharField(max_length=12, choices=Disposition.choices)
    amount = models.DecimalField(**MONEY, default=0)
    refund_case = models.ForeignKey("payments.RefundCase", null=True, blank=True, on_delete=models.PROTECT,
                                    related_name="shop_returns")
    reason = models.CharField(max_length=200, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order_id", "pk"]
        constraints = [models.CheckConstraint(condition=Q(quantity__gte=1, amount__gte=0),
                                              name="shop_order_return_amounts")]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError(gettext("Shop returns are append-only."))
        return super().save(*args, **kwargs)
