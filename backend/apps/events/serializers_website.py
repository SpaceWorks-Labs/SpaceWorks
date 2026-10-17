"""Explicit input/output contracts; object keys never cross the API boundary."""

from rest_framework import serializers

from .models_website import EventPageSection
from .serializers_website_content import HttpLinkField, WebsitePageFields
from .website_content import SPONSOR_TIERS

VISIBILITY = (("draft", "Draft"), ("published", "Published"))


class WebsiteSectionInput(serializers.Serializer):
    kind = serializers.ChoiceField(choices=EventPageSection.Kind.choices)
    slug = serializers.SlugField(max_length=80)
    title = serializers.CharField(max_length=200)
    body = serializers.CharField(max_length=10000, allow_blank=True, default="")
    url = HttpLinkField(default="")
    headline = serializers.CharField(max_length=200, allow_blank=True, required=False)
    organization = serializers.CharField(max_length=200, allow_blank=True, required=False)
    website_url = HttpLinkField(required=False)
    linkedin_url = HttpLinkField(required=False)
    x_url = HttpLinkField(required=False)
    sponsor_tier = serializers.ChoiceField(choices=SPONSOR_TIERS, required=False)
    icon = serializers.CharField(max_length=40, allow_blank=True, required=False)
    asset_id = serializers.IntegerField(min_value=1, allow_null=True, default=None)
    visibility = serializers.ChoiceField(choices=VISIBILITY, default="draft")
    position = serializers.IntegerField(min_value=0, max_value=1000, default=0)


class WebsiteSessionInput(serializers.Serializer):
    session_id = serializers.UUIDField(required=False)
    slug = serializers.SlugField(max_length=80)
    title = serializers.CharField(max_length=200)
    body = serializers.CharField(max_length=10000, allow_blank=True, default="")
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    track = serializers.SlugField(max_length=80, allow_null=True, default=None)
    room = serializers.SlugField(max_length=80, allow_null=True, default=None)
    speakers = serializers.ListField(child=serializers.SlugField(max_length=80), max_length=20, default=list)
    visibility = serializers.ChoiceField(choices=VISIBILITY, default="draft")


class WebsiteContentInput(WebsitePageFields):
    revision = serializers.IntegerField(min_value=0)
    sections = WebsiteSectionInput(many=True, max_length=100)
    sessions = WebsiteSessionInput(many=True, max_length=200)

    def validate_sections(self, value):
        if sum(row["kind"] == "room" for row in value) > 30:
            raise serializers.ValidationError("A page can have at most 30 rooms.")
        return value


class WebsiteReleaseInput(serializers.Serializer):
    released = serializers.BooleanField()
    revision = serializers.IntegerField(min_value=1)


class WebsiteDelayInput(serializers.Serializer):
    revision = serializers.IntegerField(min_value=1, required=False)
    session_id = serializers.UUIDField(required=False)
    delay_minutes = serializers.IntegerField(min_value=0, max_value=1440)


class WebsiteAssetInput(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0, required=False)
    file = serializers.FileField()
    alt_text = serializers.CharField(max_length=200)
    replace_id = serializers.IntegerField(min_value=1, required=False)


class WebsiteAssetSerializer(serializers.Serializer):
    pinned = serializers.BooleanField(required=False)
    id = serializers.IntegerField()
    alt_text = serializers.CharField()
    size_bytes = serializers.IntegerField()


class WebsiteSectionSerializer(WebsiteSectionInput):
    body_rendering = serializers.ChoiceField(choices=("restricted_v1", "legacy_literal_v1"), required=False)
    image_url = serializers.CharField(allow_null=True)
    image_alt_text = serializers.CharField(allow_blank=True)


class WebsiteSessionSerializer(WebsiteSessionInput):
    body_rendering = serializers.ChoiceField(choices=("restricted_v1", "legacy_literal_v1"), required=False)
    delay_minutes = serializers.IntegerField()
    effective_starts_at = serializers.DateTimeField()
    effective_ends_at = serializers.DateTimeField()


class WebsiteSerializer(WebsitePageFields):
    cover = serializers.DictField(child=serializers.CharField(allow_null=True), allow_null=True, required=False)
    presentation = serializers.JSONField(required=False)
    capabilities = serializers.DictField(child=serializers.BooleanField(), required=False)
    draft_revision_id = serializers.UUIDField(allow_null=True, required=False)
    published_revision_id = serializers.UUIDField(allow_null=True, required=False)
    delay_targets = serializers.ListField(child=serializers.DictField(), required=False)
    revision = serializers.IntegerField()
    released = serializers.BooleanField()
    inherited = serializers.BooleanField()
    sections = WebsiteSectionSerializer(many=True)
    sessions = WebsiteSessionSerializer(many=True)
    assets = WebsiteAssetSerializer(many=True, required=False)
