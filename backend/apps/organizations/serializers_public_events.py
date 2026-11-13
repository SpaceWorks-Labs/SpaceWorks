"""Optional Events extension of the global organization public contract."""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from apps.events.serializers_public import PublicEventSerializer
from .serializers_public import OrganizationEventHostSerializer, OrganizationArchiveEventSerializer


class PublicOrganizationEventSerializer(PublicEventSerializer):
    event_url = serializers.SerializerMethodField()
    host = OrganizationEventHostSerializer(source="makerspace", read_only=True)

    @extend_schema_field(serializers.URLField())
    def get_event_url(self, obj):
        from apps.makerspaces.public_page_access import canonical_origin
        return f"{canonical_origin(obj.makerspace)}/e/{obj.public_token}"



class PublicOrganizationEventListSerializer(serializers.Serializer):
    period = serializers.ChoiceField(choices=("upcoming", "past"))
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = PublicOrganizationEventSerializer(many=True)



class OrganizationArchiveListSerializer(PublicOrganizationEventListSerializer):
    results = OrganizationArchiveEventSerializer(many=True)

