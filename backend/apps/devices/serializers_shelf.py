"""Shelf-pointer staff serializers (decision 331): coverage, show/clear and shelf checks. None of them carries a pose."""
from rest_framework import serializers

from apps.devices.models import ShelfCheck
from apps.devices.serializers_identity import StrictSerializer

TARGETS = ["storage_location", "item", "box"]


class ShelfTargetSerializer(StrictSerializer):
    target_type = serializers.ChoiceField(choices=TARGETS)
    target_id = serializers.CharField(max_length=64)


class ShelfCoverageRequestSerializer(StrictSerializer):
    targets = ShelfTargetSerializer(many=True, max_length=200)


class ShelfCoverageSerializer(serializers.Serializer):
    target_type = serializers.CharField()
    target_id = serializers.CharField()
    covered = serializers.BooleanField()


class ShelfCoverageResponseSerializer(serializers.Serializer):
    results = ShelfCoverageSerializer(many=True)


class ShelfShowSerializer(ShelfTargetSerializer):
    mode = serializers.ChoiceField(choices=["point", "light"], default="point")
    duration_seconds = serializers.IntegerField(min_value=1, max_value=600, required=False, default=15)
    color = serializers.CharField(max_length=16, required=False, allow_blank=True, default="")


class ShelfClearSerializer(StrictSerializer):
    target_type = serializers.ChoiceField(choices=TARGETS, required=False, default="")
    target_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")


class ShelfResultSerializer(serializers.Serializer):
    sent = serializers.IntegerField(help_text="How many pointers were told (never a pose).")


class ShelfLocationSerializer(serializers.Serializer):
    location = serializers.CharField()
    item_count = serializers.IntegerField()
    covered = serializers.BooleanField()


class ShelfCheckEntrySerializer(StrictSerializer):
    location = serializers.CharField(max_length=200)
    status = serializers.ChoiceField(choices=["ok", "attention"])
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class ShelfCheckWriteSerializer(StrictSerializer):
    scope_label = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    entries = ShelfCheckEntrySerializer(many=True, min_length=1, max_length=500)


class ShelfCheckSerializer(serializers.ModelSerializer):
    checked_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ShelfCheck
        fields = ("id", "scope_label", "ok_count", "attention_count", "checked_by_name", "created_at")
        read_only_fields = fields

    def get_checked_by_name(self, obj) -> str:
        user = obj.checked_by
        return (user.get_full_name() or user.get_username()) if user else ""


class ShelfCheckDetailSerializer(ShelfCheckSerializer):
    class Meta(ShelfCheckSerializer.Meta):
        fields = ShelfCheckSerializer.Meta.fields + ("entries",)
        read_only_fields = fields
