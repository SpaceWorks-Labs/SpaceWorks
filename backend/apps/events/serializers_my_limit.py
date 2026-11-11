"""The caller's own track/window limit on a single event read (prefills the staff invite form)."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


class MyLimitSerializer(serializers.Serializer):
    track_ids = serializers.ListField(child=serializers.IntegerField())
    valid_from = serializers.DateTimeField(allow_null=True)
    valid_until = serializers.DateTimeField(allow_null=True)


class EventMyLimitField(serializers.Serializer):
    my_limit = serializers.SerializerMethodField(
        help_text="The caller's own track/time limit as a delegating co-organizer; null when unlimited, "
                  "not delegating, or on list reads (only single-event reads compute it).")

    @extend_schema_field(MyLimitSerializer(allow_null=True))
    def get_my_limit(self, obj):
        if not self.context.get("with_my_limit"):
            return None
        from .staff_grant_limits import my_limit
        return my_limit(getattr(self.context.get("request"), "user", None), obj)
