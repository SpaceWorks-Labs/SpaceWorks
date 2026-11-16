"""Member-facing L4 shapes (consent, erasure, history, refund estimate, public plans).

Nothing here carries staff notes, staff-written reasons or another person's data.
"""
from rest_framework import serializers
from apps.payments.money_fields import MoneyField

from apps.makerspaces.models import MembershipConsent, MembershipErasureRequest, MembershipPlan


class ConsentPurposeSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField(allow_blank=True)


class ConsentRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipConsent
        fields = ("id", "purpose", "notice_version", "source", "given_at", "withdrawn_at")
        read_only_fields = fields


class ConsentLedgerSerializer(serializers.Serializer):
    purposes = ConsentPurposeSerializer(many=True)
    notice_version = serializers.CharField(allow_blank=True)
    consents = ConsentRowSerializer(many=True)


class ConsentPurposeInputSerializer(serializers.Serializer):
    purpose = serializers.CharField(max_length=64)


class ErasureRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipErasureRequest
        # `member_note` is the member's own words; shown back to them only.
        fields = ("id", "status", "member_note", "decision_note", "created_at", "decided_at")
        read_only_fields = fields


class ErasureInputSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class TimelineEntrySerializer(serializers.Serializer):
    at = serializers.DateTimeField()
    kind = serializers.CharField()
    text = serializers.CharField()
    plan = serializers.CharField(allow_blank=True)
    until = serializers.DateTimeField(allow_null=True)
    lifetime = serializers.BooleanField()
    reason = serializers.CharField(allow_blank=True)


class RefundSuggestionSerializer(serializers.Serializer):
    applies = serializers.BooleanField()
    suggested_amount = MoneyField(max_digits=13, decimal_places=3, allow_null=True)
    currency = serializers.CharField()
    band = serializers.CharField(allow_blank=True)
    rule = serializers.CharField(allow_blank=True)


class PublicPlanSerializer(serializers.ModelSerializer):
    """A listed plan as the public sees it (X5): no internal limits or reminder rules."""
    renewal_price = MoneyField(max_digits=13, decimal_places=3, read_only=True)
    joining_fee = serializers.SerializerMethodField()
    application_schema = serializers.SerializerMethodField()
    join_fields = serializers.SerializerMethodField()

    class Meta:
        model = MembershipPlan
        fields = ("id", "slug", "name", "description", "plan_type", "interval", "custom_days", "fixed_end_date",
                  "amount", "renewal_price", "currency", "joining_fee", "join_mode", "sort_order", "application_schema",
                  "join_fields")
        read_only_fields = fields

    def get_join_fields(self, obj) -> dict:
        """What the join form collects for this plan (parity O-B2): photo off/optional/required, phone and state
        hidden/optional/required. Every value is off/hidden while the space's switches are off."""
        from apps.makerspaces.membership_join_fields import modes
        return modes(obj.makerspace, obj)

    def get_application_schema(self, obj) -> dict | list | None:
        """The plan's own form (X9), staff-only questions removed; null = the space form."""
        from apps.makerspaces.membership_plan_policy import public_schema
        from apps.makerspaces.platform import feature_enabled
        if not obj.application_schema or not feature_enabled(obj.makerspace, "membership.application_form"):
            return None
        return public_schema(obj.application_schema)

    def get_joining_fee(self, obj) -> str | None:
        fee = self.context.get("fees", {}).get(obj.pk)
        return None if fee is None else str(fee)
