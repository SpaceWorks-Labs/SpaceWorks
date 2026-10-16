"""Strict website allow-lists. Editorial content is deliberately publication data."""

from collections.abc import Mapping
from rest_framework import serializers

from .models import BookableSpace
from .models_website import BookingResourcePageSection
from .serializers_public import PublicBookableSpaceSerializer


class StrictInput(serializers.Serializer):
    def to_internal_value(self, data):
        unknown = set(data) - self.fields.keys() if isinstance(data, Mapping) else set()
        if unknown:
            # A field-keyed map: DRF does not wrap errors raised from a top-level
            # to_internal_value, and a bare list breaks serializer.errors.
            raise serializers.ValidationError({key: ["Unknown field."] for key in sorted(unknown)})
        return super().to_internal_value(data)


class BookingWebsiteSectionInput(StrictInput):
    kind = serializers.ChoiceField(choices=BookingResourcePageSection.Kind.choices)
    slug = serializers.SlugField(max_length=80)
    title = serializers.CharField(max_length=200)
    body = serializers.CharField(max_length=10000, allow_blank=True, default="")
    url = serializers.URLField(max_length=500, allow_blank=True, default="")
    asset_id = serializers.IntegerField(min_value=1, allow_null=True, default=None)
    visibility = serializers.ChoiceField(choices=("draft", "published"), default="draft")
    position = serializers.IntegerField(min_value=0, max_value=1000, default=0)

    def validate_url(self, value):
        if value and not value.lower().startswith(("http://", "https://")):
            raise serializers.ValidationError("Use an HTTP or HTTPS link.")
        return value


class BookingWebsiteSectionSerializer(BookingWebsiteSectionInput):
    image_url = serializers.CharField(allow_null=True)
    image_alt_text = serializers.CharField(allow_blank=True)


class BookingWebsiteContentInput(StrictInput):
    revision = serializers.IntegerField(min_value=0)
    sections = BookingWebsiteSectionInput(many=True, max_length=100)


class BookingWebsiteReleaseInput(StrictInput):
    revision = serializers.IntegerField(min_value=1)
    released = serializers.BooleanField()


class BookingWebsiteAssetInput(StrictInput):
    file = serializers.FileField()
    alt_text = serializers.CharField(max_length=200)
    replace_id = serializers.IntegerField(min_value=1, required=False)


class BookingWebsiteAssetSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    alt_text = serializers.CharField()
    size_bytes = serializers.IntegerField()


class BookingWebsiteSerializer(serializers.Serializer):
    public_url = serializers.URLField(read_only=True)
    embed_path = serializers.CharField(read_only=True)
    revision = serializers.IntegerField()
    released = serializers.BooleanField()
    sections = BookingWebsiteSectionSerializer(many=True)
    assets = BookingWebsiteAssetSerializer(many=True, required=False)


class BookingPublicRulesSerializer(serializers.Serializer):
    minimum_minutes = serializers.IntegerField()
    maximum_minutes = serializers.IntegerField()
    lead_minutes = serializers.IntegerField()
    advance_days = serializers.IntegerField()
    cancellation_cutoff_hours = serializers.IntegerField()


class PublicBookingResourceSerializer(PublicBookableSpaceSerializer):
    image_url = serializers.CharField(allow_blank=True)
    payment_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    rules = BookingPublicRulesSerializer()
    website = BookingWebsiteSerializer(allow_null=True)


class BookingDiscoveryFilters(StrictInput):
    q = serializers.CharField(max_length=200, allow_blank=True, required=False)
    location = serializers.CharField(max_length=255, allow_blank=True, required=False)
    kind = serializers.ChoiceField(choices=BookableSpace.Kind.choices, required=False)
    page = serializers.IntegerField(min_value=1, required=False)
