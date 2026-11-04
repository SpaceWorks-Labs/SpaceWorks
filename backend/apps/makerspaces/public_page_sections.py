"""Strict, bounded v1 section payloads shared by typed owner adapters."""

import math
from urllib.parse import urlsplit
from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers as s
from .public_page_markdown import public_url, validate_markdown


class StrictSerializer(s.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise s.ValidationError("Expected an object.")
        unknown = set(data) - set(self.fields)
        if unknown:
            raise s.ValidationError({key: "Unknown field." for key in sorted(unknown)})
        return super().to_internal_value(data)


class URL(s.CharField):
    def __init__(self, **kwargs):
        super().__init__(max_length=500, allow_blank=True, **kwargs)

    def to_internal_value(self, value):
        return public_url(super().to_internal_value(value))


class Titled(StrictSerializer):
    title = s.CharField(max_length=200, allow_blank=True)


class About(Titled):
    markdown = s.CharField(max_length=10000, allow_blank=True, trim_whitespace=False)

    def validate_markdown(self, value):
        return validate_markdown(value)


class GalleryItem(StrictSerializer):
    asset_id = s.IntegerField(min_value=1)
    caption = s.CharField(max_length=300, allow_blank=True)


class Gallery(Titled):
    items = GalleryItem(many=True, max_length=24)


class TeamEntry(StrictSerializer):
    id = s.UUIDField()
    kind = s.ChoiceField(choices=("explicit", "member"))
    role = s.CharField(max_length=120, allow_blank=True)
    display_name = s.CharField(max_length=200, required=False)
    url = URL(required=False)
    profile_id = s.IntegerField(min_value=1, required=False)

    def validate(self, data):
        if data["kind"] == "member":
            if "profile_id" not in data or set(data) & {"display_name", "url"}:
                raise s.ValidationError("Member entries require only profile_id, id and role.")
        elif "display_name" not in data or "profile_id" in data:
            raise s.ValidationError("Explicit entries require display_name and cannot contain profile_id.")
        return data


@extend_schema_serializer(component_name="PageTeam")
class Team(Titled):
    entries = TeamEntry(many=True, max_length=40)


class Testimonial(StrictSerializer):
    id = s.UUIDField()
    quote = s.CharField(max_length=2000)
    attribution = s.CharField(max_length=200)


class Testimonials(Titled):
    entries = Testimonial(many=True, max_length=20)


@extend_schema_serializer(component_name="PageLink")
class Link(StrictSerializer):
    id = s.UUIDField()
    label = s.CharField(max_length=80)
    platform = s.ChoiceField(choices=("website", "github", "linkedin", "instagram", "youtube", "x", "other"))
    url = URL()

    def validate(self, data):
        public_url(data["url"], allow_blank=False)
        hosts = {"github": ("github.com",), "linkedin": ("linkedin.com", "www.linkedin.com"),
                 "instagram": ("instagram.com", "www.instagram.com"),
                 "youtube": ("youtube.com", "www.youtube.com", "youtu.be"),
                 "x": ("x.com", "www.x.com", "twitter.com", "www.twitter.com")}
        if data["platform"] in hosts and urlsplit(data["url"]).hostname not in hosts[data["platform"]]:
            raise s.ValidationError({"url": "URL does not match this platform."})
        return data


class Links(Titled):
    entries = Link(many=True, max_length=20)


class Stats(Titled):
    show_public_inventory_units = s.BooleanField()
    show_published_event_count = s.BooleanField()
    publish_public_member_count = s.BooleanField()


class Location(Titled):
    enabled_publicly = s.BooleanField()
    source = s.ChoiceField(choices=("makerspace_public", "entered"))
    address = s.CharField(max_length=500, allow_blank=True, required=False)
    map_url = URL(required=False)
    latitude = s.FloatField(min_value=-90, max_value=90, allow_null=True, required=False)
    longitude = s.FloatField(min_value=-180, max_value=180, allow_null=True, required=False)
    directions = s.CharField(max_length=2000, allow_blank=True, required=False)

    def validate(self, data):
        for key in ("latitude", "longitude"):
            if data.get(key) is not None and not math.isfinite(data[key]):
                raise s.ValidationError({key: "Use a finite coordinate."})
        if (data.get("latitude") is None) != (data.get("longitude") is None):
            raise s.ValidationError("Provide both coordinates or neither.")
        if data["source"] == "makerspace_public" and set(data) - {"title", "source", "enabled_publicly"}:
            raise s.ValidationError("Public makerspace location does not accept copied coordinates.")
        return data


PAYLOADS = {"about": About, "gallery": Gallery, "team": Team, "testimonials": Testimonials,
            "links": Links, "stats": Stats, "location": Location, "upcoming_events": Titled,
            "linked_makerspaces": Titled, "organization_events": Titled,
            "functional_content": StrictSerializer, "membership_plans": Titled}
