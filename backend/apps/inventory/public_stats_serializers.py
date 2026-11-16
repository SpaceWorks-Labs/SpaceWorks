"""Response schema of the public stats page (#170), extending the legacy section shapes."""

from rest_framework import serializers

from apps.inventory.serializers import (
    PublicStatsCurrentLoanSerializer,
    PublicStatsHardwareSerializer,
    PublicStatsSerializer,
)


class PublicCountSerializer(serializers.Serializer):
    value = serializers.IntegerField(allow_null=True, help_text="Null while suppressed.")
    suppressed = serializers.BooleanField(help_text="True: below 3, shown as \"fewer than 3\".")


class PublicStatsMetricSerializer(serializers.Serializer):
    key = serializers.CharField()
    section = serializers.CharField()
    label = serializers.CharField()
    kind = serializers.ChoiceField(choices=["count", "hours"])
    value = serializers.FloatField(allow_null=True)
    suppressed = serializers.BooleanField()


class PublicStatsPeriodSerializer(serializers.Serializer):
    key = serializers.CharField(help_text="month, year, all or fy.")
    label = serializers.CharField()
    start = serializers.DateTimeField(allow_null=True)
    end = serializers.DateTimeField(allow_null=True)


class PublicStatsEventCardSerializer(serializers.Serializer):
    public_token = serializers.UUIDField()
    title = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    image_url = serializers.URLField(allow_null=True)


class PublicStatsEventsSerializer(serializers.Serializer):
    upcoming = PublicStatsEventCardSerializer(many=True)
    upcoming_count = PublicCountSerializer(allow_null=True)
    held = PublicCountSerializer(allow_null=True, help_text="Listed public events that started in the period.")
    attendees = PublicCountSerializer(allow_null=True, help_text="Checked-in attendees of those events.")


class PublicStatsCommunitySerializer(serializers.Serializer):
    active_members = PublicCountSerializer(allow_null=True)
    new_members = PublicCountSerializer(allow_null=True)
    bookings = PublicCountSerializer(allow_null=True)
    checkins = PublicCountSerializer(allow_null=True)


class PublicStatsTvSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    refresh_seconds = serializers.IntegerField()


class PublicStatsPageSerializer(PublicStatsSerializer):
    hardware = PublicStatsHardwareSerializer(read_only=True, allow_null=True)
    current_loans = PublicStatsCurrentLoanSerializer(many=True, read_only=True, allow_null=True)
    events = PublicStatsEventsSerializer(read_only=True, allow_null=True)
    community = PublicStatsCommunitySerializer(read_only=True, allow_null=True)
    sections = serializers.ListField(child=serializers.CharField(), read_only=True,
                                     help_text="Shown sections in the Space Manager's order.")
    period = PublicStatsPeriodSerializer(read_only=True)
    headline = PublicStatsMetricSerializer(many=True, read_only=True)
    metrics = PublicStatsMetricSerializer(many=True, read_only=True)
    visibility = serializers.DictField(child=serializers.BooleanField(), read_only=True)
    tv = PublicStatsTvSerializer(read_only=True)
