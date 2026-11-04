from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.inventory import public_image_storage
from apps.organizations.models import Organization


class PublicOrganizationSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    catalogue_links = serializers.SerializerMethodField()
    collections = serializers.SerializerMethodField()
    canonical_url = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = (
            "slug",
            "name",
            "description",
            "website",
            "logo_url",
            "catalogue_links",
            "collections",
            "canonical_url",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_logo_url(self, obj):
        return public_image_storage.public_url(obj.logo_key) or None

    @extend_schema_field(serializers.URLField())
    def get_canonical_url(self, obj):
        from apps.makerspaces.public_page_access import canonical_url
        claim = getattr(obj, "public_handle", None)
        page = getattr(obj, "public_page", None)
        handle = claim.handle if claim and page and page.published_revision_id else None
        return canonical_url("organization", obj, handle)

    @extend_schema_field(
        serializers.DictField(child=serializers.CharField())
    )
    def get_catalogue_links(self, obj):
        from apps.separability.registry import runtime_active
        result = {"makerspaces": f"/api/v1/public/organizations/{obj.slug}/makerspaces/"}
        if runtime_active("events"):
            result["events"] = f"/api/v1/public/organizations/{obj.slug}/events/"
        return result

    @extend_schema_field(serializers.JSONField())
    def get_collections(self, obj):
        from apps.makerspaces.public_page_derived import derived_payload
        values = {key: derived_payload("organization", obj, key, {"title": ""})
                  for key in ("linked_makerspaces", "organization_events")}
        return {key: value for key, value in values.items() if value is not None}


class OrganizationEventHostSerializer(serializers.Serializer):
    slug = serializers.SlugField(read_only=True)
    name = serializers.CharField(read_only=True)
    logo_url = serializers.SerializerMethodField()

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_logo_url(self, obj):
        return public_image_storage.public_url(obj.logo_key) or None




class OrganizationArchiveHostSerializer(serializers.Serializer):
    name = serializers.CharField()
    canonical_url = serializers.CharField()


class OrganizationArchiveEventSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=("archive",))
    title = serializers.CharField()
    description = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    timezone = serializers.CharField()
    host = OrganizationArchiveHostSerializer()
    event_url = serializers.CharField(allow_null=True)


class OrganizationSpaceSerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.CharField()
    logo_url = serializers.CharField(allow_null=True)
    canonical_url = serializers.CharField()






class OrganizationSpaceListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = OrganizationSpaceSerializer(many=True)


def __getattr__(name):
    # Keep old import paths without loading an optional app for static org pages.
    names = {"PublicOrganizationEventSerializer", "PublicOrganizationEventListSerializer", "OrganizationArchiveListSerializer"}
    if name in names:
        from apps.separability.registry import runtime_active
        if runtime_active("events"):
            from .serializers_public_events import (
                PublicOrganizationEventSerializer, PublicOrganizationEventListSerializer, OrganizationArchiveListSerializer,
            )
            return {"PublicOrganizationEventSerializer": PublicOrganizationEventSerializer,
                    "PublicOrganizationEventListSerializer": PublicOrganizationEventListSerializer,
                    "OrganizationArchiveListSerializer": OrganizationArchiveListSerializer}[name]
    raise AttributeError(name)
