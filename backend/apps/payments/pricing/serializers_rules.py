"""API shapes for item overrides, discount rules, loan fee waivers and damage/lost charges."""

from django.utils.translation import gettext
from rest_framework import serializers

from apps.accounts.pii_presentation import PiiMaskingSerializerMixin
from apps.payments.models_pricing import PriceOverride, PricingDomain
from apps.payments.models_pricing_rules import LoanFeeWaiver, PriceDiscount


class PriceOverrideComponentSerializer(serializers.Serializer):
    component = serializers.CharField()
    label = serializers.CharField()
    unit = serializers.CharField()
    has_cap = serializers.BooleanField()
    mode = serializers.ChoiceField(choices=PriceOverride.Mode.choices)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    cap = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    effective_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    effective_source = serializers.CharField()
    default_amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class PriceOverrideCardSerializer(serializers.Serializer):
    target_type = serializers.ChoiceField(choices=PriceOverride.TargetType.choices)
    target_id = serializers.IntegerField()
    label = serializers.CharField()
    domain = serializers.CharField()
    currency = serializers.CharField()
    editable = serializers.BooleanField()
    enabled = serializers.BooleanField()
    components = PriceOverrideComponentSerializer(many=True)


class PriceOverrideWriteSerializer(serializers.Serializer):
    component = serializers.CharField(max_length=32)
    mode = serializers.ChoiceField(choices=PriceOverride.Mode.choices)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False, allow_null=True)
    cap = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False, allow_null=True)

    def validate(self, attrs):
        if attrs["mode"] == PriceOverride.Mode.CUSTOM and attrs.get("amount") is None:
            raise serializers.ValidationError({"amount": gettext("Enter the custom price.")})
        return attrs


class PriceDiscountSerializer(PiiMaskingSerializerMixin, serializers.ModelSerializer):
    # A member-specific rule names an account: masked for a superadmin without a window.
    pii_account_fields = ("member_name",)
    plan_name = serializers.CharField(source="plan.name", read_only=True, allow_null=True, default=None)
    member_name = serializers.SerializerMethodField()
    domains = serializers.ListField(child=serializers.ChoiceField(choices=PricingDomain.choices), required=False)
    components = serializers.ListField(child=serializers.CharField(max_length=32), required=False)

    class Meta:
        model = PriceDiscount
        fields = ("id", "name", "audience", "plan", "plan_name", "member", "member_name", "domains", "components",
                  "percent_bps", "amount_off", "starts_at", "ends_at", "is_active", "archived_at", "created_at",
                  "updated_at")
        read_only_fields = ("id", "archived_at", "created_at", "updated_at")

    def get_fields(self):
        """Plans and members are chosen from this space only (no cross-space id probing)."""
        fields = super().get_fields()
        space = self.context.get("makerspace")
        if space is not None:
            from apps.accounts.models import User
            from apps.makerspaces.models import MembershipPlan
            fields["plan"].queryset = MembershipPlan.objects.filter(makerspace=space)
            fields["member"].queryset = User.objects.filter(
                makerspace_memberships__makerspace=space, makerspace_memberships__status="active").distinct()
        return fields

    def get_member_name(self, rule) -> str | None:
        if not rule.member_id:
            return None
        return rule.member.display_name or rule.member.get_full_name() or rule.member.username

    def validate(self, attrs):
        if attrs.get("percent_bps") is not None and attrs.get("amount_off") is not None:
            raise serializers.ValidationError({"detail": gettext("Choose a percentage or an amount, not both."),
                                               "code": "discount_invalid"})
        return attrs


class LoanFeeWaiverSerializer(PiiMaskingSerializerMixin, serializers.ModelSerializer):
    pii_account_fields = ("created_by_name",)
    created_by_name = serializers.SerializerMethodField()
    revoked = serializers.SerializerMethodField()
    covered = serializers.SerializerMethodField()

    class Meta:
        model = LoanFeeWaiver
        fields = ("id", "request", "components", "covered", "reason", "revokes", "revoked", "created_by",
                  "created_by_name", "created_at")
        read_only_fields = fields

    def get_created_by_name(self, row) -> str:
        user = row.created_by
        return user.display_name or user.get_full_name() or user.username

    def get_revoked(self, row) -> bool:
        return not row.is_revocation and hasattr(row, "revocation")

    def get_covered(self, row) -> list[str]:
        return sorted(row.covered())


class LoanFeeWaiverCreateSerializer(serializers.Serializer):
    components = serializers.ListField(child=serializers.ChoiceField(choices=LoanFeeWaiver.Component.choices),
                                       required=False, allow_empty=True)
    reason = serializers.CharField(max_length=500, allow_blank=True)


class LoanFeeWaiverRevokeSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, allow_blank=True)


class LoanFeeWaiverResultSerializer(serializers.Serializer):
    waiver = LoanFeeWaiverSerializer()
    waived_payment_ids = serializers.ListField(child=serializers.IntegerField())
    refund_case_ids = serializers.ListField(child=serializers.IntegerField())


class LoanChargeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    subject_type = serializers.CharField()
    subject_id = serializers.IntegerField()
    label = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


class LoanAccountabilityRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    issue_type = serializers.CharField()
    quantity = serializers.IntegerField()
    item_label = serializers.CharField(allow_null=True)
    has_return_photo = serializers.BooleanField()
    suggested_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    suggested_source = serializers.CharField()
    charge = LoanChargeSerializer(allow_null=True)
    no_charge_decided = serializers.BooleanField(help_text="Staff recorded \"no charge\" for this row.")


class LoanChargesSerializer(serializers.Serializer):
    request_id = serializers.IntegerField()
    currency = serializers.CharField()
    pricing_enabled = serializers.BooleanField()
    charges_enabled = serializers.BooleanField(help_text="Loan charges are tracked (charges.enabled + "
                                               "charges.loans). False: the space lends for free and no "
                                               "damage/lost charge can be raised.")
    waivers_enabled = serializers.BooleanField()
    can_waive = serializers.BooleanField()
    charges = LoanChargeSerializer(many=True)
    waivers = LoanFeeWaiverSerializer(many=True)
    accountability = LoanAccountabilityRowSerializer(many=True)


class LoanAccountabilityChargeSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class LoanAccountabilityChargeResultSerializer(serializers.Serializer):
    charge = LoanChargeSerializer(allow_null=True)
    free_reason = serializers.CharField(allow_null=True)
