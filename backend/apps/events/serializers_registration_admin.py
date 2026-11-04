from rest_framework import serializers
from apps.events.models import EventRegistration
from apps.admin_api.serializers_payment_summary import PaymentSummaryMixin
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from apps.operations.cancellation_restore import restore_deadline


class AttendanceReplySummarySerializer(serializers.Serializer):
    answer = serializers.CharField(allow_null=True)
    note = serializers.CharField()
    replied_at = serializers.DateTimeField(allow_null=True)
    effect = serializers.CharField()


class EventRegistrationAdminSerializer(PaymentSummaryMixin, serializers.ModelSerializer):
    custom_answers = serializers.JSONField(read_only=True, allow_null=True)
    event_id = serializers.IntegerField(read_only=True)
    ticket_type_id = serializers.IntegerField(read_only=True, allow_null=True)
    no_longer_eligible = serializers.BooleanField(read_only=True, default=False)
    payment = serializers.SerializerMethodField()
    restore_until = serializers.SerializerMethodField()
    # Lane L21a: the crew flag and the "still coming?" reply (X43), in the guest list and at the desk.
    is_crew = serializers.BooleanField(read_only=True)
    attendance_reply = serializers.SerializerMethodField()

    class Meta:
        model = EventRegistration
        fields = (
            'no_longer_eligible', 'id', 'event_id', 'name', 'email', 'phone', 'custom_answers',
            'status', 'created_at', 'payment', 'ticket_type_id', 'quoted_amount', 'discount_amount',
            'cancelled_at', 'status_before_cancel', 'restore_until', 'is_crew', 'attendance_reply',
        )
        read_only_fields = fields

    @extend_schema_field(AttendanceReplySummarySerializer(allow_null=True))
    def get_attendance_reply(self, obj):
        reply = getattr(obj, "attendance_reply", None) if hasattr(obj, "attendance_reply") else None
        if reply is None:
            return None
        return {"answer": reply.answer or None, "note": reply.note, "replied_at": reply.replied_at,
                "effect": reply.effect}

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_restore_until(self, obj):
        from apps.events.services_registration_tools import has_registration_consumption
        deadline = restore_deadline(obj)
        if (obj.status == "cancelled" and obj.status_before_cancel in
                ("registered", "waitlisted", "pending_approval") and deadline
                and timezone.now() < deadline and obj.event.registration_audience != "invite"
                and not has_registration_consumption(obj)):
            from apps.payments.models import Payment
            has_charge = getattr(obj, "restore_has_charge", None)
            if has_charge is None:
                has_charge = Payment.objects.filter(
                    subject_type=Payment.SubjectType.EVENT_REGISTRATION,
                    subject_id=obj.pk, makerspace_id=obj.event.makerspace_id,
                ).exists()
            if not has_charge:
                return deadline
        return None


from .serializers_registration_form import RegistrationFormInput


class EventStaffRegistrationSerializer(RegistrationFormInput):
    """Staff registering an identified account under the event's audience rules.

    `member_id` only. Contact details are copied off the account by the registration
    service, so a staffer cannot record an attendee under a name and email that belong
    to nobody — which is what makes the attendee list usable as an accountability record
    rather than free text.
    """

    member_id = serializers.IntegerField(min_value=1)
    invite_code = serializers.CharField(max_length=128, required=False, write_only=True)
    ticket_type_id = serializers.IntegerField(min_value=1, required=False)
    promo_code = serializers.CharField(max_length=128, required=False, write_only=True)
    custom_answers = serializers.JSONField(required=False, allow_null=True)
    # Used only when the account carries no number of its own. A registration must have
    # a contact number, so without this a member who never entered one could not be
    # registered by anybody — a dead end the person at the desk can simply ask about.
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default='')
    # Same fallback shape, for the same reason: `EventRegistration.email` is non-blank,
    # and a walk-in may have been created with a name and nothing else. Without this,
    # exactly the members this program made registrable could never be registered.
    email = serializers.EmailField(required=False, allow_blank=True, default='')


class EventEligibleMemberSerializer(serializers.Serializer):
    """A picker row. Name and id only — a roster is not a contact export."""

    member_id = serializers.IntegerField(min_value=1)
    display_name = serializers.CharField()
