"""Typed shape of the "Waiting on me" counters (decision 242)."""

from rest_framework import serializers


class AttentionLinkSerializer(serializers.Serializer):
    tab = serializers.CharField(help_text="Console tab key the client resolves with its own tab-path helper.")
    filters = serializers.DictField(child=serializers.CharField())


class AttentionItemSerializer(serializers.Serializer):
    key = serializers.CharField()
    count = serializers.IntegerField()
    link = AttentionLinkSerializer()


class AttentionAreaSerializer(serializers.Serializer):
    key = serializers.ChoiceField(choices=["lending", "machines", "events", "bookings", "shop", "people", "money", "safety"])
    total = serializers.IntegerField()
    items = AttentionItemSerializer(many=True)


class AttentionWaitingSerializer(AttentionItemSerializer):
    area = serializers.CharField()


class AttentionSerializer(serializers.Serializer):
    class Meta:
        ref_name = "DashboardAttention"

    areas = AttentionAreaSerializer(many=True)
    waiting = AttentionWaitingSerializer(many=True, help_text="Non-zero items across areas, largest first.")
    errors = serializers.ListField(child=serializers.CharField(), help_text="Areas whose counters failed to load.")
