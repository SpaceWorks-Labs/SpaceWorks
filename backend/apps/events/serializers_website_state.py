"""Typed event-only controls; editor authority never enters public responses."""

from drf_spectacular.utils import extend_schema_field, PolymorphicProxySerializer
from rest_framework import serializers as s
from apps.makerspaces.public_page_contract import BASE_TYPES, Document, SectionsField, INPUT_SECTION_TYPES
from apps.makerspaces.public_page_projected_serializers import ProjectedDocument, ProjectedSections, PROJECTED_TYPES


@extend_schema_field(PolymorphicProxySerializer(component_name="EventEditorialSectionInput",
    serializers={key: INPUT_SECTION_TYPES[key] for key in BASE_TYPES}, resource_type_field_name="type", many=True))
class EventEditorialSections(SectionsField):
    pass


class EventEditorialDocument(Document):
    sections = EventEditorialSections()


@extend_schema_field(PolymorphicProxySerializer(component_name="PublicEventEditorialSection",
    serializers={key: PROJECTED_TYPES[key] for key in BASE_TYPES}, resource_type_field_name="type", many=True))
class PublicEventEditorialSections(ProjectedSections):
    pass


class PublicEventEditorialDocument(ProjectedDocument):
    sections = PublicEventEditorialSections()


class WebsiteCapabilities(s.Serializer):
    can_edit_details = s.BooleanField()
    can_publish_schedule = s.BooleanField()


class WebsiteDelayTarget(s.Serializer):
    session_id = s.UUIDField()
    working_slug = s.CharField(allow_null=True)
    public_slug = s.CharField(allow_null=True)
    working_present = s.BooleanField()
    public_present = s.BooleanField()
    working_delay_minutes = s.IntegerField(allow_null=True, min_value=0, max_value=1440)
    public_delay_minutes = s.IntegerField(allow_null=True, min_value=0, max_value=1440)


class WebsiteGroupVisibility(s.Serializer):
    HERO = s.BooleanField()
    ABOUT = s.BooleanField()
    HIGHLIGHTS = s.BooleanField()
    SCHEDULE = s.BooleanField()
    SPEAKERS = s.BooleanField()
    SPONSORS = s.BooleanField()
    VENUE = s.BooleanField()
    FAQ = s.BooleanField()
    RESOURCES = s.BooleanField()
    EDITORIAL = s.BooleanField()


@extend_schema_field(WebsiteGroupVisibility)
class WebsiteGroupVisibilityInput(s.DictField):
    def __init__(self, **kwargs):
        super().__init__(child=s.BooleanField(), **kwargs)
