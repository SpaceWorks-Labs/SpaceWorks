"""Typed OpenAPI representation of the registry's validated F1 chart spec."""

from rest_framework import serializers


class ReportChartAxisSerializer(serializers.Serializer):
    field = serializers.CharField()
    kind = serializers.ChoiceField(choices=["time", "category"])


class ReportChartValueSerializer(serializers.Serializer):
    field = serializers.CharField()
    unit = serializers.CharField()
    kind = serializers.ChoiceField(choices=["line", "stacked_bar"], required=False,
                                   help_text="Optional series rendering: exclusive status counts stack; cumulative rates use lines.")


class ReportChartTruncationSerializer(serializers.Serializer):
    top_n = serializers.IntegerField(min_value=1)
    other_label = serializers.CharField()


class ReportChartSpecSerializer(serializers.Serializer):
    series = serializers.ListField(child=serializers.CharField())
    x = ReportChartAxisSerializer()
    values = ReportChartValueSerializer(many=True, help_text="Empty for detail tables without numeric measures.")
    currency_field = serializers.CharField(allow_null=True)
    partition = serializers.ChoiceField(choices=["tenant", "currency", "unit"], allow_null=True)
    negatives = serializers.ChoiceField(choices=["allow", "clip"])
    truncation = ReportChartTruncationSerializer(allow_null=True)
    alt_template = serializers.CharField()
