"""Departure input/history, booking issues and the cross-space requests queue projections."""

from rest_framework import serializers

from .models_departure import DepartureOutcome, DepartureSource
from .services_departure import MAX_REMARK


class DepartureInputSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=DepartureOutcome.choices)
    remark = serializers.CharField(max_length=MAX_REMARK, required=False, allow_blank=True, default="")

    def to_internal_value(self, data):
        if hasattr(data, "keys") and set(data.keys()) - {"outcome", "remark"}:
            raise serializers.ValidationError({key: "Unexpected field." for key in set(data.keys()) - {"outcome", "remark"}})
        return super().to_internal_value(data)


class BookingDepartureSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=DepartureOutcome.choices)
    remark = serializers.CharField(allow_blank=True)
    source = serializers.ChoiceField(choices=DepartureSource.choices)
    recorded_at = serializers.DateTimeField()
    recorded_by = serializers.SerializerMethodField()

    def get_recorded_by(self, obj) -> str:
        actor = obj.actor
        return actor.get_full_name() or actor.username


class BookingQueueFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=("pending", "confirmed", "rejected", "cancelled", "completed", "no_show", "all"),
                                     required=False, default="pending")
    space = serializers.IntegerField(min_value=1, required=False)
    ordering = serializers.ChoiceField(choices=("starts_at", "-starts_at", "created_at", "-created_at"),
                                       required=False, default="starts_at")


class BookingIssueSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    booking_id = serializers.IntegerField()
    space_id = serializers.IntegerField(source="booking.space_id")
    space_name = serializers.CharField(source="booking.space.name")
    booker_name = serializers.CharField(source="booking.name")
    starts_at = serializers.DateTimeField(source="booking.starts_at")
    ends_at = serializers.DateTimeField(source="booking.ends_at")
    outcome = serializers.ChoiceField(choices=DepartureOutcome.choices)
    remark = serializers.CharField(source="departure.remark")
    source = serializers.CharField(source="departure.source")
    created_at = serializers.DateTimeField()
    resolved_at = serializers.DateTimeField(allow_null=True)
    resolution_note = serializers.CharField(allow_blank=True)


class BookingIssuePageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    open_count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = BookingIssueSerializer(many=True)


class BookingIssueFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=("open", "resolved", "all"), required=False, default="open")
    space = serializers.IntegerField(min_value=1, required=False)


class IssueResolveSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
