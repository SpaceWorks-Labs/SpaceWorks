"""The only anonymous profile projection. Explicit fields prevent accidental PII leaks."""

from rest_framework import serializers
from .public_profile_validation import SkillSerializer, HttpsLinkSerializer


class PublicTimelineSerializer(serializers.Serializer):
    kind = serializers.CharField()
    title = serializers.CharField()
    organization = serializers.CharField()
    location = serializers.CharField()
    start = serializers.DateField()
    end = serializers.DateField(allow_null=True)
    description = serializers.CharField()
    order = serializers.IntegerField()


class PublicProjectSerializer(serializers.Serializer):
    title = serializers.CharField()
    subtitle = serializers.CharField()
    description = serializers.CharField()
    tags = serializers.ListField(child=serializers.CharField())
    image_url = serializers.CharField(allow_null=True)
    links = HttpsLinkSerializer(many=True)


class PublicVouchSerializer(serializers.Serializer):
    handle = serializers.CharField()
    display_name = serializers.CharField()


class PublicProfileSerializer(serializers.Serializer):
    viewer_is_owner = serializers.BooleanField()
    handle = serializers.CharField()
    display_name = serializers.CharField()
    avatar_url = serializers.CharField(allow_null=True)
    verified = serializers.BooleanField()
    headline = serializers.CharField()
    institution = serializers.CharField()
    bio = serializers.CharField()
    domains = serializers.ListField(child=serializers.CharField())
    skills = SkillSerializer(many=True)
    links = HttpsLinkSerializer(many=True)
    timeline = PublicTimelineSerializer(many=True)
    projects = PublicProjectSerializer(many=True)
    vouched_by = PublicVouchSerializer(many=True)
    vouched_count = serializers.IntegerField()
    show_activity_graph = serializers.BooleanField()
    show_events = serializers.BooleanField()
    show_speaking = serializers.BooleanField()
    show_projects = serializers.BooleanField()
    show_machine_activity = serializers.BooleanField()
    show_bookings = serializers.BooleanField()
    show_loans = serializers.BooleanField()


class PublicEventSerializer(serializers.Serializer):
    title = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    badge = serializers.ChoiceField(choices=["ATTENDED", "HOSTED", "SPOKE"])
    host = serializers.CharField()


class DailyBucketSerializer(serializers.Serializer):
    date = serializers.DateField()
    count = serializers.IntegerField()
    families = serializers.DictField(child=serializers.IntegerField())


class PublicActivitySerializer(serializers.Serializer):
    from_ = serializers.DateField(source="from")
    to = serializers.DateField()
    timezone = serializers.CharField()
    days = DailyBucketSerializer(many=True)

    def get_fields(self):
        fields = super().get_fields()
        fields["from"] = fields.pop("from_")
        fields["from"].source = None
        return fields


class PublicProjectPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = PublicProjectSerializer(many=True)


class PublicEventPageSerializer(PublicProjectPageSerializer):
    results = PublicEventSerializer(many=True)
