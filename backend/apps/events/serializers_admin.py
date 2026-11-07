from django.utils.translation import gettext
from collections.abc import Mapping

from rest_framework import serializers
from .models import Event
from apps.forms_schema.serializers import CustomFormSchemaField
from .serializers_public_surface import EventPublicSurfaceInput

from .serializers_registration_admin import (
    EventRegistrationAdminSerializer, EventStaffRegistrationSerializer, EventEligibleMemberSerializer,
)


class EventWriteSerializer(EventPublicSurfaceInput, serializers.Serializer):
    accent_preset = serializers.ChoiceField(choices=Event.ACCENT_CHOICES, allow_blank=True, required=False)
    registration_audience = serializers.ChoiceField(choices=Event.RegistrationAudience.choices, required=False)
    category_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    tags = serializers.ListField(child=serializers.CharField(max_length=50), max_length=20, required=False)
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(allow_blank=True, default='', required=False)
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    timezone_name = serializers.CharField(max_length=64, required=False)
    location = serializers.CharField(
        allow_blank=True,
        default='',
        max_length=255,
        required=False,
    )
    location_kind = serializers.ChoiceField(
        choices=Event.LocationKind.choices,
        default=Event.LocationKind.OTHER,
        required=False,
    )
    custom_form = CustomFormSchemaField(allow_null=True, required=False)
    capacity = serializers.IntegerField(default=0, min_value=0, required=False)
    payment_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        default=0,
        required=False,
    )
    is_public = serializers.BooleanField(default=False, required=False)
    show_registration_count = serializers.BooleanField(default=True, required=False)
    registration_requires_approval = serializers.BooleanField(
        default=False, required=False,
    )
    cancellation_cutoff_hours = serializers.IntegerField(
        allow_null=True, default=None, min_value=0, max_value=8760, required=False,
        help_text="Member cancellation closes this many hours before start; null means start.",
    )
    registration_cutoff_at = serializers.DateTimeField(
        allow_null=True, default=None, required=False,
    )
    registration_cutoff_lead_minutes = serializers.IntegerField(
        allow_null=True, default=None, min_value=0, required=False,
    )
    inherit_fields = serializers.ListField(
        child=serializers.ChoiceField(choices=sorted((
            'title', 'description', 'starts_at', 'ends_at', 'location',
            'location_kind', 'custom_form', 'capacity', 'is_public', 'payment_amount',
            'registration_requires_approval', 'registration_audience', 'registration_cutoff_at',
            'registration_cutoff_lead_minutes', 'cancellation_cutoff_hours',
            'image_key',
        ))),
        required=False,
        write_only=True,
    )

    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            return super().to_internal_value(data)
        # Preserve DRF's read-only-field behavior for these server-owned values.
        # They are ignored and never enter validated_data or transition services.
        unknown = set(data) - set(self.fields) - {"status", "makerspace", "created_by"}
        if unknown:
            raise serializers.ValidationError({key: "Unexpected field." for key in unknown})
        return super().to_internal_value(data)

    def validate(self, attrs):
        starts_at = attrs.get('starts_at', getattr(self.instance, 'starts_at', None))
        ends_at = attrs.get('ends_at', getattr(self.instance, 'ends_at', None))
        if starts_at is not None and ends_at is not None and ends_at < starts_at:
            raise serializers.ValidationError(
                {'ends_at': gettext('End time must be at or after start time.')}
            )
        cutoff_at = attrs.get(
            'registration_cutoff_at',
            getattr(self.instance, 'registration_cutoff_at', None),
        )
        lead_minutes = attrs.get(
            'registration_cutoff_lead_minutes',
            getattr(self.instance, 'registration_cutoff_lead_minutes', None),
        )
        if cutoff_at is not None and lead_minutes is not None:
            raise serializers.ValidationError({
                'registration_cutoff_at': (
                    gettext('Clear lead minutes before setting an absolute cutoff.')
                ),
                'registration_cutoff_lead_minutes': (
                    gettext('Clear the absolute cutoff before setting lead minutes.')
                ),
            })
        if cutoff_at is not None and starts_at is not None and cutoff_at > starts_at:
            raise serializers.ValidationError({
                'registration_cutoff_at': (
                    gettext('Registration cutoff cannot be after the event starts.')
                )
            })
        return attrs


class EventCreateSerializer(EventWriteSerializer):
    """Create-only extras; PATCH keeps using the dedicated organizer/partner routes."""

    organization_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), max_length=50, required=False,
        help_text="Organizer organizations. Each must be one the actor actively belongs to.",
    )
    audience_organization_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), max_length=50, required=False,
        help_text="Selected audience organizations, chosen from the organization directory.",
    )
    collaborator_slugs = serializers.ListField(
        child=serializers.SlugField(), max_length=50, required=False,
        help_text="Partner makerspaces to invite; each must accept before its members can register.",
    )
    host_makerspace_id = serializers.IntegerField(
        min_value=1, required=False,
        help_text="Host the event in another space where the actor holds event authority "
                  "(GET admin/events/host-options/). Defaults to the space in the URL.",
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        for key in ("organization_ids", "audience_organization_ids", "collaborator_slugs"):
            if len(attrs.get(key, ())) != len(set(attrs.get(key, ()))):
                raise serializers.ValidationError({key: gettext("Values must be unique.")})
        return attrs


from .serializers_event_details import (
    EventAdminSerializer, EventRegistrationCountsSerializer, EventAttendanceMarkSerializer,
)
from .serializers_admin_responses import (
    EmptyActionSerializer, EventListResponseSerializer, EventListWithDefaultsSerializer,
    EventRegistrationListResponseSerializer,
)
