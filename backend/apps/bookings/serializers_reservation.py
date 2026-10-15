"""Staff-only booking projection; scanner projections live on their own surface."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from apps.admin_api.serializers_payment_summary import PaymentSummaryMixin
from .models import Booking


class BookingAdminSerializer(PaymentSummaryMixin, serializers.ModelSerializer):
    space_id = serializers.IntegerField(read_only=True)
    payment = serializers.SerializerMethodField()

    cancelled_at = serializers.DateTimeField(read_only=True, allow_null=True)
    status_before_cancel = serializers.CharField(read_only=True)
    restore_until = serializers.SerializerMethodField()

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_restore_until(self, obj):
        from django.utils import timezone
        from apps.operations.cancellation_restore import restore_deadline
        from apps.payments.models import Payment
        from .services_restore import RESTORABLE
        if obj.status != "cancelled" or obj.status_before_cancel not in RESTORABLE:
            return None
        deadline = restore_deadline(obj)
        if deadline is None or not obj.cancelled_at <= timezone.now() < deadline:
            return None
        charged = getattr(obj, "restore_has_charge", None)
        if charged is None:
            charged = Payment.objects.filter(makerspace_id=obj.space.makerspace_id,
                subject_type=Payment.SubjectType.BOOKING, subject_id=obj.pk).exists()
        return None if charged else deadline

    class Meta:
        model = Booking
        fields = (
            'id',
            'public_token',
            'space_id',
            'name',
            'email',
            'phone',
            'starts_at',
            'ends_at',
            'status',
            'note',
            'custom_answers',
            'cancelled_at', 'status_before_cancel', 'restore_until',
            'created_at',
            'payment',
        )
        read_only_fields = fields


