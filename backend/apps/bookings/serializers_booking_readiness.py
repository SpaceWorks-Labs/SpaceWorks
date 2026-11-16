"""Schemas for the read-only staff booking readiness preview (decision 216 item 4)."""

from django.utils.translation import gettext
from rest_framework import serializers


class StaffBookingReadinessQuerySerializer(serializers.Serializer):
    member_id = serializers.IntegerField(min_value=1, max_value=9223372036854775807, required=False)
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()

    def validate(self, attrs):
        if attrs['ends_at'] <= attrs['starts_at']:
            raise serializers.ValidationError({'ends_at': gettext('End time must be after start time.')})
        return attrs


class ReadinessCheckSerializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=['room_outage', 'machine_repair', 'machine_lockout', 'certification'])
    state = serializers.ChoiceField(
        choices=['ok', 'blocked', 'warning'],
        help_text='`blocked` is a refusal the booking would meet at admission; `warning` is advisory.')
    detail = serializers.CharField()
    certifications = serializers.ListField(
        child=serializers.CharField(), required=False,
        help_text='Missing certification names; only on a blocked `certification` check.')


class MaintenanceLinkSerializer(serializers.Serializer):
    machine_id = serializers.IntegerField()


class BookingReadinessSerializer(serializers.Serializer):
    ready = serializers.BooleanField(help_text='No check is `blocked`. Submit still re-verifies everything.')
    checks = ReadinessCheckSerializer(many=True, help_text='Only the checks that apply to this resource.')
    maintenance_link = MaintenanceLinkSerializer(
        allow_null=True,
        help_text="The machine whose maintenance record this actor may open; null when the machine is not "
                  "under repair or locked out, `machines.maintenance` is off, or the actor lacks scope "
                  "over this machine.")
