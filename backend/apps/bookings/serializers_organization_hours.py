"""Open item B13: request and response shapes of the organization hours bank routes."""
from rest_framework import serializers

from .models_organization_hours import OrganizationHoursAllowance, OrganizationHoursLedger


class OrganizationHoursBankSerializer(serializers.Serializer):
    organization_id = serializers.IntegerField()
    makerspace_id = serializers.IntegerField()
    makerspace_name = serializers.CharField(required=False, help_text="Present on the organization-admin list.")
    configured = serializers.BooleanField(help_text="False until staff set an allowance for this organization.")
    allowance_minutes = serializers.IntegerField(help_text="The base allowance per period.")
    period = serializers.ChoiceField(choices=OrganizationHoursAllowance.Period.choices)
    period_key = serializers.CharField(help_text="`all`, `YYYY-MM` or `YYYY`: the period this balance is for.")
    period_ends_at = serializers.CharField(allow_null=True, help_text="ISO end of the period; null if it never resets.")
    pool_minutes = serializers.IntegerField(help_text="Allowance plus grants and adjustments this period.")
    used_minutes = serializers.IntegerField(help_text="Minutes held by bookings this period (consume minus release).")
    remaining_minutes = serializers.IntegerField()


class OrganizationHoursBankWriteSerializer(serializers.Serializer):
    allowance_minutes = serializers.IntegerField(min_value=0, max_value=6000000, required=False)
    period = serializers.ChoiceField(choices=OrganizationHoursAllowance.Period.choices, required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Send allowance_minutes, period or both.")
        return attrs


class OrganizationHoursLedgerRowSerializer(serializers.ModelSerializer):
    booking_id = serializers.IntegerField(read_only=True, allow_null=True)
    actor_name = serializers.SerializerMethodField(help_text="Staff-only; absent for organization admins.")

    class Meta:
        model = OrganizationHoursLedger
        fields = ("id", "entry", "minutes", "period_key", "booking_id", "reason", "actor_name", "created_at")
        read_only_fields = fields

    def get_actor_name(self, row) -> str:
        actor = row.actor
        if actor is None or not self.context.get("staff"):
            return ""
        return actor.display_name or actor.get_full_name() or actor.username

    def to_representation(self, row):
        data = super().to_representation(row)
        if not self.context.get("staff"):
            data.pop("actor_name", None)
        return data


class OrganizationHoursLedgerPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = OrganizationHoursLedgerRowSerializer(many=True)


class OrganizationHoursAdjustSerializer(serializers.Serializer):
    entry = serializers.ChoiceField(choices=[("grant", "grant"), ("adjust", "adjust")])
    minutes = serializers.IntegerField(min_value=-6000000, max_value=6000000,
                                       help_text="Signed; a grant must be positive.")
    reason = serializers.CharField(max_length=500, allow_blank=False)


class OrganizationHoursBanksSerializer(serializers.Serializer):
    banks = OrganizationHoursBankSerializer(many=True)
