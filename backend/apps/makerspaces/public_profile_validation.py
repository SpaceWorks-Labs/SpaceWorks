"""Public publication boundaries, separate from the member directory contract."""

from django.utils.translation import gettext
from urllib.parse import urlsplit
from rest_framework import serializers
from .models_profiles import ProfileTimelineEntry


class HttpsLinkSerializer(serializers.Serializer):
    kind = serializers.CharField(max_length=60)
    url = serializers.URLField(max_length=500)

    def validate_url(self, value):
        parsed = urlsplit(value)
        if parsed.scheme != "https" or parsed.username or parsed.password:
            raise serializers.ValidationError(gettext("Use an HTTPS link without credentials."))
        return value


class SkillSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=60)
    level = serializers.IntegerField(min_value=1, max_value=3)


class PublicationWriteSerializer(serializers.Serializer):
    public_visible = serializers.BooleanField(required=False)
    publication_consent = serializers.BooleanField(required=False, write_only=True)
    show_activity_graph = serializers.BooleanField(required=False)
    show_events = serializers.BooleanField(required=False)
    show_speaking = serializers.BooleanField(required=False)
    show_projects = serializers.BooleanField(required=False)
    show_machine_activity = serializers.BooleanField(required=False)
    show_bookings = serializers.BooleanField(required=False)
    show_loans = serializers.BooleanField(required=False)
    domains = serializers.ListField(child=serializers.CharField(max_length=60), max_length=20, required=False)
    skills = SkillSerializer(many=True, max_length=30, required=False)
    links = HttpsLinkSerializer(many=True, max_length=10, required=False)


class TimelineWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfileTimelineEntry
        fields = ("id", "kind", "title", "organization", "location", "start", "end", "description", "order")
        read_only_fields = ("id",)
        extra_kwargs = {"description": {"max_length": 4000}}

    def validate(self, attrs):
        start = attrs.get("start", getattr(self.instance, "start", None))
        end = attrs.get("end", getattr(self.instance, "end", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end": gettext("End must be on or after start.")})
        return attrs


PUBLICATION_FIELDS = (
    "public_visible", "show_activity_graph", "show_events", "show_speaking", "show_projects",
    "show_machine_activity", "show_bookings", "show_loans", "domains", "skills", "links",
)


def apply_publication(profile, data):
    from django.utils import timezone
    if data.get("public_visible") and not profile.public_visible:
        if data.get("publication_consent") is not True:
            raise serializers.ValidationError({"publication_consent": gettext("Fresh consent is required to publish.")})
        profile.public_consented_at = timezone.now()
    if data.get("public_visible") is False:
        profile.public_consented_at = None
    for field in PUBLICATION_FIELDS:
        if field in data:
            setattr(profile, field, data[field])
    profile.save(update_fields=[*PUBLICATION_FIELDS, "public_consented_at", "updated_at"])
