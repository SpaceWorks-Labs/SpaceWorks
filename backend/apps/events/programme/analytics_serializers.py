"""Typed funnel record for G's existing analytics report union."""

from rest_framework import serializers


class FunnelStageSerializer(serializers.Serializer):
    key = serializers.ChoiceField(choices=("responded", "going", "checked_in", "feedback"))
    label = serializers.CharField()
    count = serializers.IntegerField(min_value=0)
    denominator = serializers.IntegerField(min_value=0, allow_null=True)
    percent = serializers.FloatField(min_value=0, max_value=100, allow_null=True)


class SignupDaySerializer(serializers.Serializer):
    date = serializers.DateField()
    count = serializers.IntegerField(min_value=0)
    previous_count = serializers.IntegerField(min_value=0)


class CapacitySerializer(serializers.Serializer):
    limit = serializers.IntegerField(min_value=0)
    going = serializers.IntegerField(min_value=0)
    remaining = serializers.IntegerField(min_value=0, allow_null=True)
    state = serializers.ChoiceField(choices=("unlimited", "over_capacity", "full", "available"))


class FunnelSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    generated_at = serializers.DateTimeField()
    timezone_name = serializers.CharField()
    stages = FunnelStageSerializer(many=True)
    timeline = SignupDaySerializer(many=True)
    capacity = CapacitySerializer()
    caveat = serializers.CharField()
    reading = serializers.CharField()
    hint = serializers.CharField()


class EventProgrammeReportSerializer(serializers.Serializer):
    report_key = serializers.ChoiceField(choices=("event-programme",))
    rows = serializers.ListField(child=serializers.ListField())
    typed_rows = FunnelSerializer(many=True)
    meta = serializers.DictField()
