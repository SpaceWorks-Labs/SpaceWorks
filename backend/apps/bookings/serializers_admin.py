from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.bookings import storage
from apps.bookings.exceptions import BookerNamesRequiresAvailability
from apps.bookings.models import BookableSpace, Booking
from apps.forms_schema.serializers import CustomFormSchemaField


class BookableSpaceWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    kind = serializers.ChoiceField(
        choices=BookableSpace.Kind.choices,
        default=BookableSpace.Kind.OTHER,
        required=False,
    )
    description = serializers.CharField(allow_blank=True, default='', required=False)
    capacity = serializers.IntegerField(default=0, min_value=0, required=False)
    location = serializers.CharField(
        allow_blank=True,
        default='',
        max_length=255,
        required=False,
    )
    is_public = serializers.BooleanField(default=False, required=False)
    show_public_availability = serializers.BooleanField(default=False, required=False)
    show_public_booker_names = serializers.BooleanField(default=False, required=False)
    # approval_mode is a booking rule; it is writable ONLY through the dedicated
    # MANAGE_MAKERSPACE booking-rules endpoint, never this MANAGE_BOOKINGS path.
    custom_form = CustomFormSchemaField(
        allow_null=True,
        required=False,
    )
    requester_notifications_enabled = serializers.BooleanField(
        allow_null=True,
        default=None,
        required=False,
    )
    payment_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        default=0,
        required=False,
    )
    # The machine type this space is booked to use; with `machines.certifications` on,
    # members then need that type's certification to book it. Settable only while
    # `machines` is installed; null clears it.
    machine_type = serializers.IntegerField(allow_null=True, min_value=1, required=False)

    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields) if isinstance(data, dict) else set()
        if unknown:
            raise serializers.ValidationError({key: "Unexpected field." for key in sorted(unknown)})
        return super().to_internal_value(data)

    def validate(self, attrs):
        availability = attrs.get(
            'show_public_availability',
            getattr(self.instance, 'show_public_availability', False),
        )
        names = attrs.get(
            'show_public_booker_names',
            getattr(self.instance, 'show_public_booker_names', False),
        )
        if names and not availability:
            raise BookerNamesRequiresAvailability()
        return attrs


class BookableSpaceAdminSerializer(serializers.ModelSerializer):
    makerspace_id = serializers.IntegerField(read_only=True)
    created_by_id = serializers.IntegerField(allow_null=True, read_only=True)
    image_url = serializers.SerializerMethodField()
    effective_requester_notifications_enabled = serializers.SerializerMethodField()

    clone_enabled = serializers.SerializerMethodField()
    staff_tools_enabled = serializers.SerializerMethodField()
    can_copy_booking_rules = serializers.SerializerMethodField()
    passes_enabled = serializers.SerializerMethodField()

    @extend_schema_field(serializers.BooleanField())
    def get_passes_enabled(self, obj):
        return self._features(obj)["passes_enabled"]

    checkin_enabled = serializers.SerializerMethodField()

    @extend_schema_field(serializers.BooleanField())
    def get_checkin_enabled(self, obj):
        return self._features(obj)["checkin_enabled"]

    recurring_enabled = serializers.SerializerMethodField()
    staff_grants_enabled = serializers.SerializerMethodField()
    broadcasts_enabled = serializers.SerializerMethodField()
    staff_permissions = serializers.SerializerMethodField()
    can_manage_grants = serializers.SerializerMethodField()
    report_features = serializers.SerializerMethodField()

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_report_features(self, obj):
        from .report_features import features_for_resource
        return features_for_resource(self.context.get("actor"), obj, self._authority(obj), self.context)

    @extend_schema_field(serializers.BooleanField())
    def get_clone_enabled(self, obj):
        return self._features(obj)["clone_enabled"]

    @extend_schema_field(serializers.BooleanField())
    def get_staff_tools_enabled(self, obj):
        return self._features(obj)["staff_tools_enabled"]

    @extend_schema_field(serializers.BooleanField())
    def get_can_copy_booking_rules(self, obj):
        from apps.accounts import rbac
        actor = self.context.get("actor")
        if actor is None:
            return False
        cache = self.context.setdefault("booking_rule_authority", {})
        if obj.makerspace_id not in cache:
            cache[obj.makerspace_id] = rbac.can(actor, rbac.Action.MANAGE_MAKERSPACE, obj.makerspace_id)
        return cache[obj.makerspace_id]

    @extend_schema_field(serializers.BooleanField())
    def get_broadcasts_enabled(self, obj):
        return self._features(obj)["broadcasts_enabled"]

    @extend_schema_field(serializers.BooleanField())
    def get_recurring_enabled(self, obj):
        return self._features(obj)["recurring_enabled"]

    @extend_schema_field(serializers.BooleanField())
    def get_staff_grants_enabled(self, obj):
        return self._features(obj)["staff_grants_enabled"]

    def _features(self, obj):
        from .booking_authority_page import features_for_page
        cache = self.context.setdefault("booking_features", {})
        if obj.makerspace_id not in cache:
            cache.update(features_for_page([obj]))
        return cache[obj.makerspace_id]

    def _authority(self, obj):
        from .booking_authority import can_manage_grants, permissions_for
        from .booking_permissions import PERMISSIONS
        cache = self.context.setdefault("booking_authority", {})
        if obj.pk not in cache:
            actor = self.context.get("actor")
            manager = can_manage_grants(actor, obj)
            cache[obj.pk] = (manager, list(PERMISSIONS) if manager else permissions_for(actor, obj))
        return cache[obj.pk]

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_staff_permissions(self, obj):
        return self._authority(obj)[1]

    @extend_schema_field(serializers.BooleanField())
    def get_can_manage_grants(self, obj):
        return self._authority(obj)[0]

    class Meta:
        model = BookableSpace
        fields = (
            "clone_enabled", "staff_tools_enabled", "can_copy_booking_rules",
            "recurring_enabled", "staff_grants_enabled", "broadcasts_enabled", "staff_permissions", "can_manage_grants",
            "report_features",
            "checkin_enabled", "passes_enabled",
            'id',
            'public_token',
            'makerspace_id',
            'name',
            'kind',
            'description',
            'capacity',
            'location',
            'image_url',
            'is_public',
            'show_public_availability',
            'show_public_booker_names',
            'approval_mode',
            'min_booking_duration_minutes',
            'max_booking_duration_minutes',
            'booking_lead_time_minutes',
            'max_booking_advance_days',
            'buffer_before_minutes',
            'buffer_after_minutes',
            'cancellation_cutoff_hours',
            'custom_form',
            'requester_notifications_enabled',
            'payment_amount',
            'machine_type',
            'effective_requester_notifications_enabled',
            'is_active',
            'created_by_id',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_blank=True))
    def get_image_url(self, obj):
        return storage.public_url(obj.image_key)

    @extend_schema_field(serializers.BooleanField())
    def get_effective_requester_notifications_enabled(self, obj):
        override = obj.requester_notifications_enabled
        if override is not None:
            return override
        return obj.makerspace.booking_requester_notifications_enabled


class BookableSpaceBookingRulesSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookableSpace
        fields = (
            'min_booking_duration_minutes',
            'max_booking_duration_minutes',
            'booking_lead_time_minutes',
            'max_booking_advance_days',
            'buffer_before_minutes',
            'buffer_after_minutes',
            'cancellation_cutoff_hours',
            'approval_mode',
        )


from .serializers_reservation import BookingAdminSerializer


class SpaceImagePresignRequestSerializer(serializers.Serializer):
    filename = serializers.CharField(max_length=255)
    content_type = serializers.CharField(max_length=100)


class SpaceImageUploadSerializer(serializers.Serializer):
    url = serializers.URLField()
    method = serializers.ChoiceField(choices=('PUT',), required=False)
    fields = serializers.DictField(required=False)
    headers = serializers.DictField(required=False)


class SpaceImagePresignResponseSerializer(serializers.Serializer):
    object_key = serializers.CharField()
    upload = SpaceImageUploadSerializer()


class SpaceImageFinalizeRequestSerializer(serializers.Serializer):
    object_key = serializers.CharField(max_length=500)


class EmptyActionSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if data:
            raise serializers.ValidationError(
                {field: 'Unexpected field.' for field in data}
            )
        return value


class BookableSpaceListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True, required=False)
    previous = serializers.CharField(allow_null=True, required=False)
    results = BookableSpaceAdminSerializer(many=True)


class BookingListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True, required=False)
    previous = serializers.CharField(allow_null=True, required=False)
    results = BookingAdminSerializer(many=True)


class BookingListFilterSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField(min_value=1, max_value=9223372036854775807, required=False)
    status = serializers.ChoiceField(choices=Booking.Status.choices, required=False)
    starts_at = serializers.DateTimeField(required=False)
    ends_at = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        if (
            attrs.get('starts_at')
            and attrs.get('ends_at')
            and attrs['ends_at'] < attrs['starts_at']
        ):
            raise serializers.ValidationError(
                {'ends_at': 'End of window must be at or after its start.'}
            )
        return attrs
