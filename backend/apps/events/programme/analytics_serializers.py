"""Typed funnel record for G's existing analytics report union."""

from rest_framework import serializers


class FunnelStageSerializer(serializers.Serializer):
    # AN-c1: one `application_stage` row per live L21a review stage, between responded and going.
    key = serializers.ChoiceField(choices=("responded", "application_stage", "going", "checked_in", "feedback"))
    label = serializers.CharField()
    stage_position = serializers.IntegerField(min_value=1, allow_null=True)
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


# Release 2 L2 (G8): per-event extras. Counts only; never people, never free text.
class ArrivalWindowSerializer(serializers.Serializer):
    window_start = serializers.DateTimeField()
    count = serializers.IntegerField(min_value=0)


class CheckinMethodSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=("online", "qr", "offline_sync", "venue_station", "legacy"))
    count = serializers.IntegerField(min_value=0)


class AnswerCountSerializer(serializers.Serializer):
    label = serializers.CharField()
    count = serializers.IntegerField(min_value=0)


class AnswerChartSerializer(serializers.Serializer):
    question_id = serializers.CharField()
    label = serializers.CharField(allow_blank=True)
    type = serializers.ChoiceField(choices=("single_choice", "dropdown", "multi_choice", "yes_no"))
    answers = AnswerCountSerializer(many=True)
    total = serializers.IntegerField(min_value=0)


class WaitlistConversionSerializer(serializers.Serializer):
    ever_waitlisted = serializers.IntegerField(min_value=0)
    promoted = serializers.IntegerField(min_value=0)
    still_waiting = serializers.IntegerField(min_value=0)
    conversion_percent = serializers.FloatField(allow_null=True)


class SeriesTurnoutSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    title = serializers.CharField()
    starts_at = serializers.DateTimeField()
    registered = serializers.IntegerField(min_value=0)
    attended = serializers.IntegerField(min_value=0)


class VisitDaySerializer(serializers.Serializer):
    day = serializers.DateField()
    count = serializers.IntegerField(min_value=0)


class EventAnalyticsExtrasSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    timezone_name = serializers.CharField()
    window_minutes = serializers.IntegerField()
    arrivals = ArrivalWindowSerializer(many=True)
    checkin_methods = CheckinMethodSerializer(many=True)
    answers = AnswerChartSerializer(many=True)
    waitlist = WaitlistConversionSerializer()
    series = SeriesTurnoutSerializer(many=True)
    short_link_visits = VisitDaySerializer(many=True, allow_null=True)
