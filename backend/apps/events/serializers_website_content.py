"""Page metadata has a typed schema even where stored as a single JSON value."""

from django.utils.translation import gettext
import math

from rest_framework import serializers

from .website_content import PAGE_GROUPS
from .serializers_website_state import WebsiteGroupVisibilityInput, EventEditorialDocument


class HttpLinkField(serializers.URLField):
    def __init__(self, **kwargs):
        super().__init__(max_length=500, allow_blank=True, **kwargs)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if value and not value.lower().startswith(("https://", "http://")):
            raise serializers.ValidationError(gettext("Use an HTTP or HTTPS link."))
        return value


class WebsiteVenueSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, allow_blank=True, default="")
    address = serializers.CharField(max_length=500, allow_blank=True, default="")
    city = serializers.CharField(max_length=200, allow_blank=True, default="")
    country = serializers.CharField(max_length=200, allow_blank=True, default="")
    latitude = serializers.FloatField(min_value=-90, max_value=90, allow_null=True, default=None)
    longitude = serializers.FloatField(min_value=-180, max_value=180, allow_null=True, default=None)
    map_url = HttpLinkField(default="")
    directions = serializers.CharField(max_length=2000, allow_blank=True, default="")
    parking = serializers.CharField(max_length=2000, allow_blank=True, default="")
    public_transport = serializers.CharField(max_length=2000, allow_blank=True, default="")
    accessibility_notes = serializers.CharField(max_length=2000, allow_blank=True, default="")

    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - self.fields.keys():
            raise serializers.ValidationError(gettext("Unknown venue fields."))
        return super().to_internal_value(data)

    def validate(self, attrs):
        for key in ("latitude", "longitude"):
            if attrs[key] is not None and not math.isfinite(attrs[key]):
                raise serializers.ValidationError({key: gettext("Use a finite coordinate.")})
        return attrs


class WebsitePageFields(serializers.Serializer):
    editorial_document = EventEditorialDocument(required=False, allow_null=True)
    # Omitted fields preserve existing content, including older editor clients.
    tagline = serializers.CharField(max_length=300, allow_blank=True, required=False)
    accent_color = serializers.RegexField(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", allow_blank=True, required=False)
    section_order = serializers.ListField(child=serializers.ChoiceField(choices=PAGE_GROUPS),
                                         min_length=len(PAGE_GROUPS)-1, max_length=len(PAGE_GROUPS), required=False)
    section_enabled = WebsiteGroupVisibilityInput(required=False)
    venue = WebsiteVenueSerializer(allow_null=True, required=False)

    def validate_section_order(self, value):
        if "EDITORIAL" not in value:
            value = [*value, "EDITORIAL"]
        if len(value) != len(PAGE_GROUPS) or set(value) != set(PAGE_GROUPS):
            raise serializers.ValidationError(gettext("List each page section exactly once."))
        return value

    def validate_editorial_document(self, value):
        from apps.makerspaces.public_page_contract import normalize_document, empty_document
        return normalize_document(value or empty_document("event"), kind="event")

    def validate_section_enabled(self, value):
        if set(value) - set(PAGE_GROUPS):
            raise serializers.ValidationError(gettext("Unknown page section."))
        return {group: value.get(group, True) for group in PAGE_GROUPS}
