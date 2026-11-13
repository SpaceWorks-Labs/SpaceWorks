"""Staff-only booking projection; scanner projections live on their own surface."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from apps.admin_api.serializers_payment_summary import PaymentSummaryMixin
from .event_labels import LINKED_EVENT_FIELD
from apps.machines.serializers_sessions import MachineEventSummarySerializer
from .models import Booking
from .serializers_departure import BookingDepartureSerializer


class BookingAdminSerializer(PaymentSummaryMixin, serializers.ModelSerializer):
    space_id = serializers.IntegerField(read_only=True)
    payment = serializers.SerializerMethodField()

    cancelled_at = serializers.DateTimeField(read_only=True, allow_null=True)
    status_before_cancel = serializers.CharField(read_only=True)
    restore_until = serializers.SerializerMethodField()
    space_name = serializers.CharField(source="space.name", read_only=True)
    event = serializers.SerializerMethodField(help_text="The event this machine-time booking is logged for (decision 342), or null.")
    decision_reason = serializers.CharField(read_only=True)
    departed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    departures = serializers.SerializerMethodField()
    open_issue_id = serializers.SerializerMethodField()
    requested_price = serializers.SerializerMethodField()
    linked_event = serializers.SerializerMethodField()
    organization_name = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField(allow_null=True, help_text=(
        "Decision 223 (k): the organization a partner-event booking was made for; null otherwise.")))
    def get_organization_name(self, obj):
        link = getattr(obj, "organization_link", None) if obj.pk else None
        if link is None:
            return None
        from .organization_booking import organization_bookings_on  # decision 218: off hides the name
        return link.organization_name if organization_bookings_on(obj.space.makerspace) else None

    @LINKED_EVENT_FIELD
    def get_linked_event(self, obj):
        # Batched by the list view (`event_labels`); every other projection omits it as null.
        return self.context.get("event_labels", {}).get(obj.pk)

    @extend_schema_field(serializers.DictField(allow_null=True, help_text=(
        "L15 (#159): {total, currency, discount_total} frozen when a booking awaiting approval was "
        "requested; approval charges exactly this. Null for instant or legacy bookings.")))
    def get_requested_price(self, obj):
        snapshot = obj.pricing_snapshot or {}
        if not snapshot:
            return None
        return {"total": snapshot.get("total"), "currency": snapshot.get("currency"),
                "discount_total": snapshot.get("discount_total")}

    @extend_schema_field(BookingDepartureSerializer(many=True))
    def get_departures(self, obj):
        # The staff list prefetches these (`departure_events` with actor); the single-row paths fall back to a query.
        prefetched = getattr(obj, "_prefetched_objects_cache", {}).get("departure_events")
        events = prefetched if prefetched is not None else obj.departure_events.select_related("actor")
        return BookingDepartureSerializer(events, many=True).data

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_open_issue_id(self, obj):
        prefetched = getattr(obj, "_prefetched_objects_cache", {}).get("issues")
        if prefetched is not None:  # list view: newest first, same order as the query below
            return next((issue.pk for issue in prefetched if issue.resolved_at is None), None)
        return obj.issues.filter(resolved_at__isnull=True).values_list("pk", flat=True).first()

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

    @extend_schema_field(MachineEventSummarySerializer(allow_null=True))
    def get_event(self, obj):
        from apps.machines.event_use import event_summary
        return event_summary(obj)

    class Meta:
        model = Booking
        fields = (
            'id',
            'public_token',
            'space_id',
            'member_id',  # decision 242 (BK2): the requester's account, for the member link
            'name',
            'email',
            'phone',
            'starts_at',
            'ends_at',
            'status',
            'arrived_at',
            'note',
            'custom_answers',
            'cancelled_at', 'status_before_cancel', 'restore_until',
            'created_at',
            'payment',
            'space_name', 'decision_reason', 'departed_at', 'departures', 'open_issue_id',
            'requested_price', 'linked_event', 'is_house', 'organization_name', 'event',
        )
        read_only_fields = fields

