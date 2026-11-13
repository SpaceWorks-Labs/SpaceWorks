"""Reject/cancel reasons: bounded staff text shown to the requester and kept in history."""

from django.utils.translation import gettext
from rest_framework import serializers

MAX_REASON = 1000


def clean_reason(value, *, required):
    reason = (value or "").strip()
    if required and not reason:
        raise serializers.ValidationError({"reason": gettext("Tell the requester why this booking is being rejected.")})
    if len(reason) > MAX_REASON:
        raise serializers.ValidationError({"reason": gettext('Keep the reason under {MAX_REASON} characters.').format(MAX_REASON=MAX_REASON)})
    return reason


class BookingDecisionSerializer(serializers.Serializer):
    """Body of reject (reason required) and cancel (reason optional); no other field is accepted."""

    reason = serializers.CharField(max_length=MAX_REASON, required=False, allow_blank=True, default="")

    def __init__(self, *args, reason_required=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.reason_required = reason_required

    def to_internal_value(self, data):
        if hasattr(data, "keys") and set(data.keys()) - {"reason"}:
            raise serializers.ValidationError({field: "Unexpected field." for field in set(data.keys()) - {"reason"}})
        value = super().to_internal_value(data)
        value["reason"] = clean_reason(value.get("reason"), required=self.reason_required)
        return value


class BookingRejectSerializer(BookingDecisionSerializer):
    reason = serializers.CharField(max_length=MAX_REASON)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, reason_required=True, **kwargs)
