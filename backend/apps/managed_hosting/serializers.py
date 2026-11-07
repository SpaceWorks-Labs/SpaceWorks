"""Managed-hosting API shapes (#187A)."""

from django.utils.translation import gettext
from django.utils import timezone
from rest_framework import serializers

from .availability import online_billing_enabled
from .models import HostingInvoice, HostingInvoiceReceipt, HostingPlan, PlatformHostingBillingSettings
from .plans import validate_limits, validate_modules


class HostingPlanSerializer(serializers.ModelSerializer):
    space_count = serializers.SerializerMethodField()

    class Meta:
        model = HostingPlan
        fields = ("id", "key", "name", "description", "is_active", "trial_days", "price_minor", "currency",
                  "billing_period", "limits", "allowed_modules", "space_count", "created_at", "updated_at")
        read_only_fields = ("id", "space_count", "created_at", "updated_at")

    def get_space_count(self, obj) -> int:
        return obj.assignments.count()

    def validate_limits(self, value):
        return validate_limits(value)

    def validate_allowed_modules(self, value):
        return validate_modules(value)


class HostingPlanAssignmentSerializer(serializers.Serializer):
    makerspace_id = serializers.IntegerField()
    plan = HostingPlanSerializer()
    assigned_at = serializers.DateTimeField()
    trial_ends_at = serializers.DateTimeField(allow_null=True)
    trial_expired = serializers.SerializerMethodField()

    def get_trial_expired(self, obj) -> bool:
        return obj.trial_expired_at is not None


class HostingPlanAssignRequestSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField()
    trial_days = serializers.IntegerField(min_value=0, max_value=365, required=False, allow_null=True, default=None)


class HostingInvoiceReceiptSerializer(serializers.ModelSerializer):
    recorded_by = serializers.SerializerMethodField()

    class Meta:
        model = HostingInvoiceReceipt
        fields = ("method", "reference", "received_on", "amount_minor", "recorded_at", "recorded_by", "note")
        read_only_fields = fields

    def get_recorded_by(self, obj) -> str | None:
        return (obj.recorded_by.display_name or obj.recorded_by.username) if obj.recorded_by else None


class HostingInvoiceSerializer(serializers.ModelSerializer):
    makerspace = serializers.SerializerMethodField()
    overdue = serializers.SerializerMethodField()
    online_payable = serializers.SerializerMethodField()
    receipts = HostingInvoiceReceiptSerializer(many=True, read_only=True)

    class Meta:
        model = HostingInvoice
        fields = ("id", "number", "makerspace", "makerspace_name", "description", "amount_minor", "currency",
                  "due_on", "period_start", "period_end", "status", "overdue", "paid_at", "voided_at",
                  "void_reason", "receipts", "online_payable", "created_at")
        read_only_fields = fields

    def get_makerspace(self, obj) -> dict | None:
        return {"id": obj.makerspace_id, "name": obj.makerspace.name} if obj.makerspace_id else None

    def get_overdue(self, obj) -> bool:
        return obj.status == HostingInvoice.Status.OPEN and obj.due_on < timezone.localdate()

    def get_online_payable(self, obj) -> bool:
        return obj.status == HostingInvoice.Status.OPEN and online_billing_enabled()


class SpaceHostingInvoiceSerializer(HostingInvoiceSerializer):
    """The Space Manager's view: who recorded a receipt stays the platform's business."""

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for receipt in data["receipts"]:
            receipt.pop("recorded_by", None)
        return data


class HostingInvoiceCreateSerializer(serializers.Serializer):
    makerspace_id = serializers.IntegerField()
    amount_minor = serializers.IntegerField(min_value=1)
    currency = serializers.RegexField(r"^[A-Za-z]{3}$")
    description = serializers.CharField(max_length=300)
    due_on = serializers.DateField()
    period_start = serializers.DateField(required=False, allow_null=True, default=None)
    period_end = serializers.DateField(required=False, allow_null=True, default=None)


class HostingInvoicePaymentSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=("bank_transfer", "cash", "cheque", "card_offline", "other"))
    reference = serializers.CharField(max_length=200)
    received_on = serializers.DateField()
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class HostingInvoiceVoidSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=3, max_length=300)


class HostingBillingSettingsSerializer(serializers.ModelSerializer):
    online_billing_switch = serializers.SerializerMethodField()
    provider = serializers.CharField(max_length=16, required=False, allow_blank=True,
                                     help_text="`stripe`, `razorpay`, or blank for none.")
    stripe_secret_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    stripe_webhook_secret = serializers.CharField(write_only=True, required=False, allow_blank=True)
    razorpay_key_secret = serializers.CharField(write_only=True, required=False, allow_blank=True)
    razorpay_webhook_secret = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = PlatformHostingBillingSettings
        fields = ("auto_enforce_enabled", "grace_days", "online_billing_switch", "provider", "razorpay_key_id",
                  *PlatformHostingBillingSettings.SECRET_FIELDS, "updated_at")
        read_only_fields = ("updated_at",)
        extra_kwargs = {"grace_days": {"min_value": 0, "max_value": 365}}

    def validate_provider(self, value):
        if value not in ("", "stripe", "razorpay"):
            raise serializers.ValidationError(gettext("Choose stripe, razorpay or none."))
        return value

    def get_online_billing_switch(self, obj) -> bool:
        return online_billing_enabled()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for field in PlatformHostingBillingSettings.SECRET_FIELDS:
            data[f"{field}_set"] = bool(getattr(instance, field))
        return data


class HostingCheckoutSerializer(serializers.Serializer):
    url = serializers.URLField()


class HostingPlanUsageRowSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    used = serializers.IntegerField(allow_null=True)
    limit = serializers.IntegerField(allow_null=True)
    unit = serializers.CharField(help_text="`bytes` or `count`.")
    percent = serializers.FloatField(allow_null=True)
    level = serializers.CharField(help_text="`ok`, `warning` (from 80 %) or `limit` (100 %).")


class HostingPlanUsageSerializer(serializers.Serializer):
    plan = serializers.DictField(allow_null=True)
    trial_ends_at = serializers.DateTimeField(allow_null=True)
    read_only_reason = serializers.CharField(allow_null=True)
    resources = HostingPlanUsageRowSerializer(many=True)
    warnings = serializers.ListField(child=serializers.CharField())
