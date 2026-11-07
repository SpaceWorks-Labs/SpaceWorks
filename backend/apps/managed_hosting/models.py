"""Managed-hosting plans, per-space assignment, and hosting billing (#187A, off by default).

All platform data: the platform operator's tiers and the platform's own invoices to a
space. None of it travels in a tenant export or dump. Invoices and receipts outlive a
purged space (``SET_NULL`` plus a name/id snapshot) because they are the platform's
financial records; receipts are append-only. Money never moves without the payer acting:
there is no stored card and no automatic charge, only a checkout the Space Manager opens.
"""

from django.utils.translation import gettext_noop
from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q

from apps.makerspaces.secrets import decrypt_value, encrypt_value


class HostingPlan(models.Model):
    class Period(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"
        NONE = "none", gettext_noop("No recurring fee")

    key = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    trial_days = models.PositiveSmallIntegerField(default=0)
    price_minor = models.PositiveIntegerField(default=0)
    currency = models.CharField(max_length=3, default="USD",
                                validators=[RegexValidator(r"^[A-Z]{3}$", "Use a 3-letter currency code.")])
    billing_period = models.CharField(max_length=8, choices=Period.choices, default=Period.MONTHLY)
    # {limit key: int | null}; absent or null = unlimited. Keys: plan_limits.PLAN_LIMIT_KEYS.
    limits = models.JSONField(default=dict, blank=True)
    # Module keys this plan allows; empty = every module.
    allowed_modules = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("price_minor", "name")

    def __str__(self):
        return self.name


class SpacePlanAssignment(models.Model):
    makerspace = models.OneToOneField("makerspaces.Makerspace", on_delete=models.CASCADE,
                                      related_name="hosting_plan_assignment")
    plan = models.ForeignKey(HostingPlan, on_delete=models.PROTECT, related_name="assignments")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="+")
    assigned_at = models.DateTimeField(auto_now=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True, db_index=True)
    trial_expired_at = models.DateTimeField(null=True, blank=True)
    # Trial reminder keys already mailed, e.g. "trial:7".
    reminders_sent = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"{self.makerspace_id}: {self.plan_id}"


class HostingInvoice(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        PAID = "paid", "Paid"
        VOID = "void", "Void"

    number = models.CharField(max_length=24, unique=True)
    makerspace = models.ForeignKey("makerspaces.Makerspace", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    makerspace_id_snapshot = models.PositiveBigIntegerField()
    makerspace_name = models.CharField(max_length=200)
    plan = models.ForeignKey(HostingPlan, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    description = models.CharField(max_length=300)
    amount_minor = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    currency = models.CharField(max_length=3)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    due_on = models.DateField(db_index=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN, db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=300, blank=True)
    provider = models.CharField(max_length=16, blank=True)
    provider_session_id = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-due_on", "-id")
        constraints = [
            models.CheckConstraint(condition=~Q(status="paid") | Q(paid_at__isnull=False),
                                   name="hosting_invoice_paid_has_time"),
            models.CheckConstraint(condition=~Q(status="void") | Q(voided_at__isnull=False),
                                   name="hosting_invoice_void_has_time"),
        ]

    def __str__(self):
        return self.number


class HostingInvoiceReceipt(models.Model):
    """How an invoice was paid: an offline receipt, or the provider's payment. Append-only."""

    class Method(models.TextChoices):
        BANK_TRANSFER = "bank_transfer", gettext_noop("Bank transfer")
        CASH = "cash", "Cash"
        CHEQUE = "cheque", "Cheque"
        CARD_OFFLINE = "card_offline", gettext_noop("Card (offline terminal)")
        OTHER = "other", "Other"
        ONLINE_STRIPE = "online_stripe", gettext_noop("Online (Stripe)")
        ONLINE_RAZORPAY = "online_razorpay", gettext_noop("Online (Razorpay)")

    invoice = models.ForeignKey(HostingInvoice, on_delete=models.PROTECT, related_name="receipts")
    method = models.CharField(max_length=16, choices=Method.choices)
    reference = models.CharField(max_length=200)
    received_on = models.DateField()
    amount_minor = models.PositiveIntegerField()
    note = models.CharField(max_length=300, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="+")
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("recorded_at", "id")
        constraints = [
            models.UniqueConstraint(fields=("method", "reference"), condition=Q(method__startswith="online_"),
                                    name="uniq_hosting_online_receipt"),
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("Hosting invoice receipts are append-only.")
        super().save(*args, **kwargs)


class PlatformHostingBillingSettings(models.Model):
    """Singleton (pk=1). Provider secrets are Fernet ciphertext, never returned."""

    auto_enforce_enabled = models.BooleanField(default=False)
    grace_days = models.PositiveSmallIntegerField(default=14)
    provider = models.CharField(max_length=16, blank=True, choices=[("", "None"), ("stripe", "Stripe"),
                                                                     ("razorpay", "Razorpay")])
    stripe_secret_key = models.TextField(blank=True)
    stripe_webhook_secret = models.TextField(blank=True)
    razorpay_key_id = models.CharField(max_length=100, blank=True)
    razorpay_key_secret = models.TextField(blank=True)
    razorpay_webhook_secret = models.TextField(blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    SECRET_FIELDS = ("stripe_secret_key", "stripe_webhook_secret", "razorpay_key_secret", "razorpay_webhook_secret")

    @classmethod
    def load(cls):
        row, _ = cls.objects.get_or_create(pk=1)
        return row

    def set_secret(self, field, raw):
        setattr(self, field, encrypt_value(raw) if raw else "")

    def secret(self, field):
        stored = getattr(self, field)
        return decrypt_value(stored) if stored else ""
