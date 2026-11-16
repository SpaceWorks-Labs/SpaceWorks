"""Typed pass contract: no arbitrary text, answers, images or QR bindings."""
from rest_framework import serializers

from apps.operations.printable_serializers import PrintInputSerializer, PositionedElementSerializer
from .pass_templates import PASS_FIELDS, normalize_pass_template


class BookingPassElementSerializer(PositionedElementSerializer):
    field = serializers.ChoiceField(choices=PASS_FIELDS)


class BookingPassTemplateSerializer(PrintInputSerializer):
    version = serializers.IntegerField(min_value=2, max_value=2, required=False)
    paper_size = serializers.ChoiceField(choices=("A4", "LETTER", "custom"), required=False)
    orientation = serializers.ChoiceField(choices=("portrait", "landscape"), required=False)
    page_width_mm = serializers.FloatField(min_value=100, max_value=500, allow_null=True, required=False)
    page_height_mm = serializers.FloatField(min_value=100, max_value=500, allow_null=True, required=False)
    card_width_mm = serializers.FloatField(min_value=40, max_value=150, required=False)
    card_height_mm = serializers.FloatField(min_value=30, max_value=120, required=False)
    margin_mm = serializers.FloatField(min_value=0, max_value=40, required=False)
    gap_mm = serializers.FloatField(min_value=0, max_value=30, required=False)
    grid_mm = serializers.FloatField(min_value=0.5, max_value=10, required=False)
    elements = BookingPassElementSerializer(many=True, min_length=1, max_length=4, required=False)

    def validate(self, attrs):
        return normalize_pass_template(attrs)
