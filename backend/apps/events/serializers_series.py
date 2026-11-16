from collections.abc import Mapping

from rest_framework import serializers
from apps.payments.money_fields import MoneyField
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field

from apps.events.models import EventSeries
from .venue import ADDRESS_MAX, validate_map_url
from apps.forms_schema.serializers import CustomFormSchemaField
from apps.inventory import public_image_storage


from .serializers_ticketing import TicketInputSerializer
from .serializers_event_authority import EventAuthorityFields

class EventSeriesWriteSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            return super().to_internal_value(data)
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: "Unexpected field." for key in unknown})
        return super().to_internal_value(data)

    registration_audience = serializers.ChoiceField(choices=("members", "accounts", "invite", "participating_organizations"), required=False)
    ticket_types = TicketInputSerializer(many=True, required=False, write_only=True)
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(allow_blank=True, default="", required=False)
    location = serializers.CharField(allow_blank=True, default="", max_length=255, required=False)
    venue_address = serializers.CharField(allow_blank=True, max_length=ADDRESS_MAX, required=False)
    venue_map_url = serializers.CharField(allow_blank=True, max_length=500, required=False,
                                          validators=[validate_map_url])
    location_kind = serializers.ChoiceField(
        choices=(('indoor', 'Indoor'), ('outdoor', 'Outdoor'), ('other', 'Other')),
        default="other", required=False,
    )
    custom_form = CustomFormSchemaField(allow_null=True, required=False)
    capacity = serializers.IntegerField(default=0, min_value=0, required=False)
    payment_amount = MoneyField(
        max_digits=13, decimal_places=3, min_value=0, default=0, required=False,
    )
    registration_requires_approval = serializers.BooleanField(default=False, required=False)
    cancellation_cutoff_hours = serializers.IntegerField(
        allow_null=True, default=None, min_value=0, max_value=8760, required=False,
    )
    registration_cutoff_lead_minutes = serializers.IntegerField(
        allow_null=True, default=None, min_value=0, required=False,
    )
    is_public = serializers.BooleanField(default=False, required=False)
    listing = serializers.ChoiceField(choices=(("listed", "Listed"), ("unlisted", "Unlisted")), required=False,
                                      help_text="Who can find new occurrences; each occurrence can change its own.")
    recurrence_timezone = serializers.CharField(max_length=64)
    dtstart_local_date = serializers.DateField()
    dtstart_local_time = serializers.TimeField()
    recurrence_rule = serializers.CharField(max_length=500)
    duration_minutes = serializers.IntegerField(min_value=1)
    effective_from = serializers.DateTimeField(required=False, write_only=True)


class EventSeriesSummarySerializer(EventAuthorityFields, serializers.ModelSerializer):
    makerspace_id = serializers.IntegerField(read_only=True)
    next_occurrence_at = serializers.SerializerMethodField()
    future_occurrence_count = serializers.SerializerMethodField()

    class Meta:
        model = EventSeries
        fields = (
            "id", "staff_permissions", "can_manage_staff", "public_token", "makerspace_id", "title", "status",
            "recurrence_timezone", "dtstart_local_date", "dtstart_local_time",
            "recurrence_rule", "duration_minutes", "revision", "next_occurrence_at",
            "future_occurrence_count", "last_materialized_at",
            "last_generation_error_code", "updated_at",
        )
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_next_occurrence_at(self, obj):
        value = getattr(obj, "next_occurrence_at", None)
        if value is not None:
            return value
        row = obj.occurrences.filter(status__in=("draft", "published")).order_by("starts_at").first()
        return row.starts_at if row else None

    @extend_schema_field(OpenApiTypes.INT)
    def get_future_occurrence_count(self, obj):
        value = getattr(obj, "future_occurrence_count", None)
        if value is not None:
            return value
        return obj.occurrences.filter(status__in=("draft", "published")).count()


from .serializers_organization_audience import OrganizationAudienceFields


class EventSeriesDetailSerializer(OrganizationAudienceFields, EventSeriesSummarySerializer):
    website_enabled = serializers.SerializerMethodField()

    @extend_schema_field(serializers.BooleanField())
    def get_website_enabled(self, obj):
        from apps.makerspaces.platform import feature_enabled
        return feature_enabled(obj.makerspace, "events.website")
    created_by_id = serializers.IntegerField(allow_null=True, read_only=True)
    image_url = serializers.SerializerMethodField()
    organization_audience_enabled = serializers.SerializerMethodField()
    money = serializers.SerializerMethodField()

    @extend_schema_field(serializers.JSONField(allow_null=True))
    def get_money(self, obj):
        """Parity C24: the series money card (per currency, over every occurrence), or null when the viewer may
        not see event money or the space tracks no event payments."""
        request = self.context.get("request")
        if request is None or request.method != "GET":
            return None  # reading the ledger is for the detail read, not every mutation response
        from apps.operations.reports_events_money import series_money
        return series_money(obj.makerspace, obj, request.user)

    @extend_schema_field(serializers.BooleanField())
    def get_organization_audience_enabled(self, obj):
        from apps.makerspaces.platform import feature_enabled
        return feature_enabled(obj.makerspace, "events.organization_audience")

    class Meta(EventSeriesSummarySerializer.Meta):
        fields = EventSeriesSummarySerializer.Meta.fields + (
            "participating_organizations", "audience_label", "organization_admission_blocked", "organization_audience_enabled",
            "website_enabled", "description", "location", "location_kind", "venue_address", "venue_map_url", "custom_form", "capacity",
            "payment_amount", "registration_requires_approval", "registration_audience",
            "cancellation_cutoff_hours",
            "registration_cutoff_lead_minutes", "is_public", "listing", "created_by_id", "created_at",
            "image_url", "money",
        )

    @extend_schema_field(OpenApiTypes.URI)
    def get_image_url(self, obj):
        return public_image_storage.public_url(obj.image_key) or None


class EventSeriesMutationResponseSerializer(serializers.Serializer):
    series = EventSeriesDetailSerializer(read_only=True)
    created_occurrence_ids = serializers.ListField(child=serializers.IntegerField(), read_only=True)
    removed_occurrence_ids = serializers.ListField(child=serializers.IntegerField(), read_only=True)
    affected_count = serializers.IntegerField(read_only=True)


class EventSeriesListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = EventSeriesSummarySerializer(many=True)
