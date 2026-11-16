"""OpenAPI shapes for the badge designer routes (E-B1)."""
from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from .serializers import CardDesignSerializer


class BadgeFieldSerializer(serializers.Serializer):
    key = serializers.CharField(help_text="A printFieldKeys value: `registration:<form key>`, `attendee:team` or `attendee:crew_kind`.")
    label = serializers.CharField()


class BadgeRoleSerializer(serializers.Serializer):
    role = serializers.CharField(help_text="attendee, crew, volunteer, speaker, mentor, judge or organiser.")
    design_id = serializers.IntegerField(allow_null=True)
    format = serializers.ChoiceField(choices=("badge_v1", "free_canvas", "none"),
                                     help_text="none = this role uses the attendee design.")
    published = serializers.BooleanField()


class BadgeDesignsSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    event_title = serializers.CharField()
    organisation_name = serializers.CharField()
    role_badges = serializers.BooleanField(help_text="`events.role_badges` is on: role variants can be made.")
    roles = BadgeRoleSerializer(many=True)
    fields = BadgeFieldSerializer(many=True, help_text="Answers the designer may print (at most `max_print_fields`).")
    max_print_fields = serializers.IntegerField()
    sponsor_limit_max = serializers.IntegerField()
    presets = serializers.ListField(child=serializers.DictField(), help_text="Portrait stock presets; 'Turn' swaps width and height.")
    templates = serializers.ListField(child=serializers.CharField())
    branding = serializers.DictField(help_text="has_organisation_logo, has_event_logo, sponsor_count.")


class BadgeRoleStartSerializer(serializers.Serializer):
    restart = serializers.BooleanField(default=False, help_text="Replace the design with a fresh badge_v1 one.")


@extend_schema_serializer(component_name="CardBadgeDesignResult")
class BadgeDesignResultSerializer(serializers.Serializer):
    design = CardDesignSerializer()
    created = serializers.BooleanField()


class BadgeImportRequestSerializer(serializers.Serializer):
    file = serializers.JSONField(help_text="The parsed design file: {kind, version, settings}. Events files are accepted as-is.")


class BadgeImportResultSerializer(serializers.Serializer):
    design = CardDesignSerializer()
    notes = serializers.ListField(child=serializers.CharField())
    unmatched_fields = serializers.ListField(child=serializers.CharField(),
                                             help_text="Imported answer keys this event's form does not have.")


class BadgeFileSerializer(serializers.Serializer):
    kind = serializers.CharField()
    version = serializers.IntegerField()
    settings = serializers.DictField()
