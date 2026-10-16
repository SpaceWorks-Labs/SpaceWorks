"""Public print geometry schema shared by separable domain adapters."""

from rest_framework import serializers

from .printable_layout import FONTS


class PrintInputSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError("Expected an object.")
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: "Unexpected field." for key in sorted(unknown)})
        return super().to_internal_value(data)


class PositionedElementSerializer(PrintInputSerializer):
    field = serializers.CharField(max_length=80)
    x_mm = serializers.FloatField(min_value=0)
    y_mm = serializers.FloatField(min_value=0)
    width_mm = serializers.FloatField(min_value=0.5)
    height_mm = serializers.FloatField(min_value=0.5)
    font = serializers.ChoiceField(choices=FONTS, required=False)
    font_size_pt = serializers.FloatField(min_value=6, max_value=48, required=False)
    bold = serializers.BooleanField(required=False)
    align = serializers.ChoiceField(choices=("left", "center", "right"), required=False)
    colour = serializers.RegexField(r"^#[0-9A-Fa-f]{6}$", required=False)
