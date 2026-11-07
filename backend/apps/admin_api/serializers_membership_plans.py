"""Serializers for the staff membership-plan, term and invitation-request surfaces."""
from django.utils.translation import gettext
import re

from rest_framework import serializers

from apps.admin_api.serializers_membership_plan_rules import validate_plan_rules
from apps.forms_schema.serializers import CustomFormSchemaField
from apps.makerspaces.models import InvitationRequest, MembershipPlan, MembershipTerm

_CURRENCY = re.compile(r"^[A-Za-z]{3}$")


class MembershipPlanSerializer(serializers.ModelSerializer):
    application_schema = CustomFormSchemaField(required=False, allow_null=True)
    renewal_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = MembershipPlan
        fields = [
            "id", "name", "interval", "custom_days", "amount", "currency", "is_active",
            "created_at", "updated_at", "loan_max_active", "loan_max_items",
            "auto_renew", "renewal_open_days", "renewal_grace_days", "renewal_retries",
            "reminder_days_before", "reminder_days_after",
            # Release 2 (G16, X5, X6, X8, X9): type, prices, per-plan overrides, listing.
            "plan_type", "fixed_end_date", "renewal_amount", "renewal_price", "joining_fee",
            "rejoin_rule", "rejoin_after_days", "payment_timing", "join_mode", "application_schema",
            "late_renewal", "slug", "description", "sort_order", "is_public", "archived_at",
        ]
        # `makerspace` comes from the URL, never the body: accepting it would let a
        # manager in one space price memberships in another.
        read_only_fields = ["id", "created_at", "updated_at", "archived_at"]

    def validate_currency(self, value):
        if not _CURRENCY.match(value or ""):
            raise serializers.ValidationError(gettext("Use a three-letter ISO 4217 code."))
        return value.lower()

    def validate(self, attrs):
        for name in ("reminder_days_before", "reminder_days_after"):
            values = attrs.get(name, [])
            if not isinstance(values, list) or len(values) > 10 or any(
                type(day) is not int or not 1 <= day <= 365 for day in values
            ):
                raise serializers.ValidationError({name: gettext("Use up to ten day offsets between 1 and 365.")})
        interval = attrs.get("interval", getattr(self.instance, "interval", None))
        custom_days = attrs.get("custom_days", getattr(self.instance, "custom_days", None))
        if interval == MembershipPlan.Interval.CUSTOM_DAYS:
            if not custom_days:
                raise serializers.ValidationError(
                    {"custom_days": gettext("Required for a custom-days interval.")}
                )
        elif custom_days is not None:
            # Silently normalising would hide a client bug; refusing keeps the row honest.
            raise serializers.ValidationError(
                {"custom_days": gettext("Only a custom-days interval takes a day count.")}
            )
        return validate_plan_rules(attrs, self.instance, self.context.get("makerspace"))


class MembershipTermSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    standing = serializers.SerializerMethodField()
    is_lifetime = serializers.BooleanField(read_only=True)

    class Meta:
        model = MembershipTerm
        fields = [
            "id", "membership", "plan", "plan_name", "starts_at", "ends_at", "status",
            "renewal_payment", "created_by", "created_at",
            # Frozen at opening (X6) and the derived standing (X7).
            "kind", "price", "joining_fee", "currency", "plan_type", "standing", "is_lifetime",
        ]
        read_only_fields = fields

    def get_standing(self, obj) -> str:
        from django.utils import timezone

        from apps.makerspaces.membership_term_history import standing
        return standing(obj, timezone.now())


class MembershipTermCreateSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField()
    starts_at = serializers.DateTimeField(required=False, allow_null=True)


class InvitationRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvitationRequest
        fields = [
            "id", "name", "email", "phone", "message", "status", "handled_by",
            "handled_at", "created_at",
        ]
        read_only_fields = fields
