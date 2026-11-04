"""The shop catalogue (release 2 L22, #128 C-7, #135): products, variants, kit parts, settings.

A product is what a buyer browses; its variants are what is sold and stocked (a product
with no options has one default variant). Each variant carries its own price and its own
stock, or draws on one item consumable of the inventory (Q-S11): workshop use and sales
then come out of ONE count, kept by the inventory availability module. Lendable tools are
never sold. A kit is its own stocked item unless it is in bundle mode (Q-S12), when a sale
takes each component's stock instead. Quantities change only in
`inventory/availability_shop.py`.
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

MONEY = {"max_digits": 12, "decimal_places": 2}


class ShopSettings(models.Model):
    """One row per space: hold windows, the returns window, reminders and buyer-facing text."""

    makerspace = models.OneToOneField("makerspaces.Makerspace", on_delete=models.CASCADE,
                                      related_name="shop_settings")
    #: Q-S4: an online checkout holds its stock this long; pay-at-desk orders hold for hours.
    online_hold_minutes = models.PositiveSmallIntegerField(default=15, validators=[MinValueValidator(5),
                                                                                    MaxValueValidator(120)])
    desk_hold_hours = models.PositiveSmallIntegerField(default=48, validators=[MinValueValidator(1),
                                                                               MaxValueValidator(720)])
    #: Q-S7: 0 means no returns.
    returns_window_days = models.PositiveSmallIntegerField(default=14, validators=[MaxValueValidator(365)])
    #: Q-S17: reminders for paid orders nobody collected, and when staff may cancel them.
    first_reminder_days = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1),
                                                                                 MaxValueValidator(90)])
    second_reminder_days = models.PositiveSmallIntegerField(default=7, validators=[MinValueValidator(1),
                                                                                  MaxValueValidator(180)])
    uncollected_cancel_days = models.PositiveSmallIntegerField(default=30, validators=[MinValueValidator(1),
                                                                                      MaxValueValidator(365)])
    #: Staff-authored, shown before payment. Never personal data.
    policy_text = models.TextField(blank=True, default="", max_length=2000)
    pickup_note = models.CharField(max_length=300, blank=True, default="")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(second_reminder_days__gt=models.F("first_reminder_days")),
                                   name="shop_settings_reminders_ordered"),
        ]

    @classmethod
    def for_makerspace(cls, makerspace):
        row = cls.objects.filter(makerspace=makerspace).first()
        return row if row is not None else cls(makerspace=makerspace)


class ShopProduct(models.Model):
    class Kind(models.TextChoices):
        CONSUMABLE = "consumable", "Consumable"
        KIT = "kit", "Kit"
        MERCH = "merch", "Merch"
        OTHER = "other", "Other"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="shop_products")
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.OTHER)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=80)
    description = models.TextField(blank=True, default="", max_length=4000)
    #: A public-bucket image (public image rules); the key is never a secret.
    image_key = models.CharField(max_length=512, blank=True, default="")
    category = models.CharField(max_length=80, blank=True, default="")
    is_public = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    unit = models.CharField(max_length=32, blank=True, default="each")
    #: Q-S16: optional per-order limit (with `shop.order_limits` on).
    max_per_order = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    #: Q-S6: only signed-in members of this space may buy it (with `shop.member_prices` on).
    members_only = models.BooleanField(default=False)
    #: Q-S14: exact stock on the public page for this product (with `shop.public_stock` on).
    show_exact_stock = models.BooleanField(default=False)
    #: Q-S2: the product's tax class (with `shop.tax` on): its rate and HSN code. NULL rate
    #: means the space's own rate. Prices are entered tax-inclusive.
    tax_rate_bps = models.PositiveIntegerField(null=True, blank=True, validators=[MaxValueValidator(10000)])
    hsn_code = models.CharField(max_length=8, blank=True, default="")
    #: Q-S12: a kit in bundle mode takes each component's stock at sale (with `shop.bundles` on).
    bundle_mode = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "slug"], name="shop_product_unique_slug"),
            models.CheckConstraint(condition=Q(tax_rate_bps__isnull=True) | Q(tax_rate_bps__lte=10000),
                                   name="shop_product_tax_rate_range"),
            models.CheckConstraint(condition=Q(bundle_mode=False) | Q(kind="kit"), name="shop_product_bundle_is_kit"),
        ]

    def __str__(self):
        return self.name


class ShopVariant(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    product = models.ForeignKey(ShopProduct, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField(max_length=120, default="Standard")
    #: Option values such as {"size": "M", "colour": "Blue"}; at most three, short strings.
    options = models.JSONField(default=dict, blank=True)
    sku = models.CharField(max_length=64, blank=True, default="")
    price = models.DecimalField(**MONEY, validators=[MinValueValidator(0)])
    #: Own stock on the shelf, and how much of it live holds are keeping for checkouts.
    on_hand = models.PositiveIntegerField(default=0)
    held = models.PositiveIntegerField(default=0)
    reorder_point = models.PositiveIntegerField(default=0)
    #: Q-S11: draw on an inventory item consumable instead of own stock.
    linked_product = models.ForeignKey("inventory.InventoryProduct", null=True, blank=True,
                                       on_delete=models.PROTECT, related_name="shop_variants")
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["product_id", "sort_order", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "sku"], condition=~Q(sku=""), name="shop_variant_unique_sku"),
            models.CheckConstraint(condition=Q(price__gte=0), name="shop_variant_price_nonnegative"),
            models.CheckConstraint(condition=Q(linked_product__isnull=False) | Q(held__lte=models.F("on_hand")),
                                   name="shop_variant_held_within_stock"),
            models.CheckConstraint(condition=Q(linked_product__isnull=True) | Q(on_hand=0),
                                   name="shop_variant_linked_has_no_own_stock"),
        ]

    def __str__(self):
        return self.name or str(self.pk)


class ShopKitComponent(models.Model):
    """One part of a bundle-mode kit: a sale of the kit takes `quantity` of this variant."""

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    kit = models.ForeignKey(ShopProduct, on_delete=models.CASCADE, related_name="components")
    component = models.ForeignKey(ShopVariant, on_delete=models.PROTECT, related_name="+")
    quantity = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        ordering = ["kit_id", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["kit", "component"], name="shop_kit_component_unique"),
            models.CheckConstraint(condition=Q(quantity__gte=1), name="shop_kit_component_positive"),
        ]
