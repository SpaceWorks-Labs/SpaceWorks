"""Refund policy shape: events and bookings by time before start, memberships by term."""

from django.utils.translation import gettext
from decimal import Decimal

from rest_framework import serializers

from apps.payments.models import RefundPolicy

MEMBERSHIP_ONLY = ("full_within_days", "partial_mode")
TIMED_ONLY = ("full_before_minutes", "partial_before_minutes")


class RefundPolicySerializer(serializers.ModelSerializer):
    configured = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    plan_name = serializers.SerializerMethodField()

    class Meta:
        model = RefundPolicy
        fields = ("area", "plan", "plan_name", "configured", "full_before_minutes", "partial_before_minutes",
                  "full_within_days", "partial_mode", "partial_percent", "cancellation_fee", "currency", "updated_at")
        read_only_fields = ("area", "plan", "plan_name", "configured", "currency", "updated_at")
        extra_kwargs = {"cancellation_fee": {"min_value": Decimal("0.00")},
                        "partial_percent": {"min_value": 0, "max_value": 100},
                        "full_before_minutes": {"max_value": 525600},
                        "partial_before_minutes": {"max_value": 525600},
                        "full_within_days": {"max_value": 3660}}

    def get_configured(self, policy) -> bool:
        return policy.pk is not None

    def get_currency(self, policy) -> str:
        return self.context.get("currency", "")

    def get_plan_name(self, policy) -> str:
        return policy.plan.name if policy.plan_id else ""

    def validate(self, attrs):
        area = self.instance.area if self.instance is not None else self.context.get("area")
        if area == RefundPolicy.Area.MEMBERSHIP:
            # A term is measured from its start, never in minutes before it.
            for name in TIMED_ONLY:
                attrs[name] = 0
        else:
            if attrs.get("partial_mode", RefundPolicy.PartialMode.PERCENT) != RefundPolicy.PartialMode.PERCENT:
                raise serializers.ValidationError({"partial_mode": gettext("Pro rata applies to memberships only.")})
            if attrs.get("full_within_days"):
                raise serializers.ValidationError({"full_within_days": gettext("Days into a term apply to memberships only.")})
            full = attrs.get("full_before_minutes", getattr(self.instance, "full_before_minutes", 0))
            partial = attrs.get("partial_before_minutes", getattr(self.instance, "partial_before_minutes", 0))
            if partial > full:
                raise serializers.ValidationError(
                    {"partial_before_minutes": gettext("The partial window cannot start before the full-refund window.")})
        fee = attrs.get("cancellation_fee")
        if fee is not None:
            from apps.payments.refund_policy import precision_ok
            if not precision_ok(fee, self.context.get("currency", "")):
                raise serializers.ValidationError({"cancellation_fee": gettext("Too many decimal places for this currency.")})
        return attrs
