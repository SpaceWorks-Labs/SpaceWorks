"""Validated contextual equipment command shapes."""
from rest_framework import serializers

from apps.hardware_requests.serializers import RequestItemInputSerializer, RequestSubmitSerializer
from django.utils.translation import gettext

MAX_SAFE_ID = 9007199254740991


class KitSelectionSerializer(serializers.Serializer):
    id = serializers.IntegerField(min_value=1, max_value=MAX_SAFE_ID)
    version = serializers.IntegerField(min_value=1, max_value=MAX_SAFE_ID)


class ContextualBaseSerializer(RequestSubmitSerializer):
    operation_id = serializers.UUIDField()
    event_registration_id = serializers.IntegerField(
        required=False, allow_null=True, default=None, min_value=1, max_value=MAX_SAFE_ID,
    )
    items = serializers.ListField(
        child=RequestItemInputSerializer(), required=False, allow_null=False,
        allow_empty=False, max_length=20,
    )
    kit = KitSelectionSerializer(required=False, allow_null=False)

    def validate(self, attrs):
        if ("items" in attrs) == ("kit" in attrs):
            raise serializers.ValidationError(gettext("Provide exactly one of items or kit."))
        attrs["website"] = attrs.get("website", "")
        if "items" in attrs:
            ids = [item["product_id"] for item in attrs["items"]]
            if any(not 0 < item <= MAX_SAFE_ID for item in ids) or len(ids) != len(set(ids)):
                raise serializers.ValidationError({"items": gettext("Invalid or duplicate product IDs.")})
        return attrs


class ContextualSelfSerializer(ContextualBaseSerializer):
    booking_token = serializers.UUIDField(required=False, allow_null=True, default=None)


class ContextualStaffSerializer(ContextualBaseSerializer):
    booking_id = serializers.IntegerField(
        required=False, allow_null=True, default=None, min_value=1, max_value=MAX_SAFE_ID,
    )
    borrower_id = serializers.IntegerField(
        required=False, allow_null=True, default=None, min_value=1, max_value=MAX_SAFE_ID,
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["event_registration_id"] is None and attrs["booking_id"] is None:
            raise serializers.ValidationError(gettext("A source is required."))
        return attrs


class ContextualSelfResultSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["request", "consumable_plan"])
    public_token = serializers.UUIDField(required=False)
    status = serializers.CharField(required=False)
    plan_id = serializers.IntegerField(required=False, min_value=1, max_value=MAX_SAFE_ID)
    replayed = serializers.BooleanField()


class ContextualStaffResultSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["request", "consumable_plan"])
    request_id = serializers.IntegerField(required=False, min_value=1, max_value=MAX_SAFE_ID)
    status = serializers.CharField(required=False)
    plan_id = serializers.IntegerField(required=False, min_value=1, max_value=MAX_SAFE_ID)
    replayed = serializers.BooleanField()
