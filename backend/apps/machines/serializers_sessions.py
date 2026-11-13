"""Shapes for machine sessions (lane L23): the member's own view and the staff view.

A session's money and review state are derived (`sessions_state`); the payment rows for
a page are looked up once by the view and passed in `context["payments"]`.
"""

from decimal import Decimal

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.pii_presentation import PiiMaskingSerializerMixin
from apps.machines import sessions_billing as billing
from apps.machines import sessions_state as state
from apps.machines.event_use import event_summary
from apps.machines.models import MachineSession, MachineSessionAmendment


class SessionRateSerializer(serializers.Serializer):
    unit_amount = serializers.CharField(help_text="Price per hour, frozen when the session started.")
    currency = serializers.CharField()
    increment = serializers.IntegerField(help_text="Billing increment in minutes (0 = per minute).")
    minimum = serializers.IntegerField(help_text="Minimum billed minutes.")
    discount_name = serializers.CharField(allow_blank=True)


class SessionPaymentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    amount = serializers.CharField()
    currency = serializers.CharField()
    status = serializers.CharField()


def rate_payload(snapshot):
    terms = billing.rate_terms(snapshot)
    if terms is None:
        return None
    return {"unit_amount": terms["unit_amount"], "currency": terms["currency"], "increment": terms["increment"],
            "minimum": terms["minimum"], "discount_name": ((snapshot or {}).get("discount") or {}).get("name", "")}


class MachineEventSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()


class MemberSessionSerializer(serializers.ModelSerializer):
    event = serializers.SerializerMethodField(help_text="The event this use is logged for (decision 342), or null.")
    machine_name = serializers.CharField(source="machine.name", read_only=True)
    machine_type_name = serializers.CharField(source="machine_type.name", read_only=True)
    status = serializers.SerializerMethodField()
    minutes = serializers.SerializerMethodField()
    charge_state = serializers.SerializerMethodField()
    rate = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    payment = serializers.SerializerMethodField()

    class Meta:
        model = MachineSession
        fields = ["id", "makerspace_id", "machine_id", "machine_name", "machine_type_name", "source", "status",
                  "started_at", "ended_at", "minutes", "stop_reason", "flagged", "charge_state", "rate", "amount",
                  "payment", "event"]
        read_only_fields = fields

    @extend_schema_field(MachineEventSummarySerializer(allow_null=True))
    def get_event(self, obj):
        return event_summary(obj)

    def _payment(self, obj):
        return (self.context.get("payments") or {}).get(obj.pk)

    def get_status(self, obj) -> str:
        return state.status(obj)

    def get_minutes(self, obj) -> int:
        if obj.ended_at is None:
            return max(int((timezone.now() - obj.started_at).total_seconds() // 60), 0)
        return state.effective_minutes(obj)

    def get_charge_state(self, obj) -> str:
        return state.charge_state(obj, self._payment(obj))

    @extend_schema_field(SessionRateSerializer(allow_null=True))
    def get_rate(self, obj):
        return rate_payload(obj.quote_snapshot) if obj.billable else None

    def get_amount(self, obj) -> str | None:
        """The charge raised, or the running / proposed amount at the frozen rate."""
        payment = self._payment(obj)
        if payment is not None:
            return str(payment.amount)
        if not obj.billable or obj.service_request_id:
            return None
        total = billing.final_quote(obj.quote_snapshot, self.get_minutes(obj)).total
        from apps.payments.money import quantize_money
        return str(quantize_money(total, (obj.quote_snapshot or {}).get("currency")))

    @extend_schema_field(SessionPaymentSerializer(allow_null=True))
    def get_payment(self, obj):
        payment = self._payment(obj)
        if payment is None:
            return None
        return {"id": payment.pk, "amount": str(payment.amount), "currency": payment.currency, "status": payment.status}


class SessionAmendmentSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = MachineSessionAmendment
        fields = ["id", "kind", "minutes", "member_id", "reason", "actor_name", "created_at"]
        read_only_fields = fields

    def get_actor_name(self, obj) -> str:
        return (obj.actor.display_name or obj.actor.username) if obj.actor_id else ""


class StaffSessionSerializer(PiiMaskingSerializerMixin, MemberSessionSerializer):
    pii_account_fields = ("member_name",)
    member_name = serializers.SerializerMethodField()
    needs_review = serializers.SerializerMethodField()
    amendments = SessionAmendmentSerializer(many=True, read_only=True)

    class Meta(MemberSessionSerializer.Meta):
        fields = MemberSessionSerializer.Meta.fields + [
            "member_id", "member_name", "needs_review", "service_request_id", "duration_minutes", "started_by_id",
            "stopped_by_id", "amendments"]
        read_only_fields = fields

    def get_member_name(self, obj) -> str:
        member = state.effective_member(obj)
        return (member.display_name or member.username) if member is not None else ""

    def get_needs_review(self, obj) -> bool:
        return state.needs_review(obj)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["member_id"] = state.effective_member_id(instance)
        return data


class SessionRefusalSerializer(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField()
    certifications = serializers.ListField(child=serializers.CharField(), required=False)


class SessionPreviewSerializer(serializers.Serializer):
    machine_id = serializers.IntegerField()
    machine_name = serializers.CharField()
    machine_type_id = serializers.IntegerField(help_text="For the type's training notes (decision 343).")
    machine_type_name = serializers.CharField()
    machine_status = serializers.CharField()
    billing = serializers.BooleanField(help_text="Whether a session here is charged.")
    rate = SessionRateSerializer(allow_null=True)
    digest = serializers.CharField(allow_blank=True, help_text="Send it back with Start; a changed price answers "
                                                                "409 price_changed.")
    max_minutes = serializers.IntegerField()
    closes_at = serializers.DateTimeField(allow_null=True)
    can_start = serializers.BooleanField()
    refusal = SessionRefusalSerializer(allow_null=True)
    live_session = MemberSessionSerializer(allow_null=True)


class SessionStartSerializer(serializers.Serializer):
    digest = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    event_id = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None,
                                        help_text="Optional: an event I may act for in this makerspace (decision 342).")


class StaffSessionStartSerializer(serializers.Serializer):
    machine_id = serializers.IntegerField(min_value=1)
    member_id = serializers.IntegerField(min_value=1)
    event_id = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None,
                                        help_text="Optional: an event the member may act for (decision 342).")


class SessionAmendSerializer(serializers.Serializer):
    minutes = serializers.IntegerField(min_value=0, max_value=24 * 60)
    reason = serializers.CharField(max_length=500, trim_whitespace=True)


class SessionAssignSerializer(serializers.Serializer):
    member_id = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=500, trim_whitespace=True)


class SessionSettingsSerializer(serializers.Serializer):
    session_max_minutes = serializers.IntegerField(min_value=5, max_value=24 * 60)
