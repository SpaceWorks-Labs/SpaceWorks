from django.utils.translation import gettext
from rest_framework import serializers

from .serializers_badge_prints import (
    BadgeDesignBundleSerializer, BadgeReceiptResultSerializer, BadgeReceiptSerializer, BadgeRowSerializer,
)


class OfflineCheckInOperationSerializer(serializers.Serializer):
    operation_id = serializers.UUIDField()
    checkin_token = serializers.CharField(max_length=64)
    reported_occurred_at = serializers.DateTimeField()


class OfflineCheckInSyncRequestSerializer(serializers.Serializer):
    lease_token = serializers.CharField(max_length=8192)
    operations = OfflineCheckInOperationSerializer(many=True, allow_empty=False)
    badge_receipts = BadgeReceiptSerializer(many=True, required=False, help_text="Badges printed while offline "
                                            "(`events.badge_desk_print`); at most 200, recorded when they sync.")

    def validate_operations(self, value):
        if len(value) > 200:
            raise serializers.ValidationError(gettext("At most 200 operations may be synchronized."))
        operation_ids = [item["operation_id"] for item in value]
        if len(operation_ids) != len(set(operation_ids)):
            raise serializers.ValidationError(gettext("Operation IDs must be unique within a batch."))
        return value


class OfflineRosterRegistrationSerializer(serializers.Serializer):
    registration_id = serializers.IntegerField()
    checkin_token = serializers.CharField(allow_null=True, help_text="A legacy UUID, or the live SWEC2 code of a v2 "
                                          "credential (badge desk print on); null when none is live.")
    name = serializers.CharField()
    host_waiver_state = serializers.ChoiceField(
        choices=["not_required", "on_file", "missing"]
    )
    checkin_payload = serializers.CharField(required=False, allow_null=True)
    badge = BadgeRowSerializer(required=False, help_text="With `events.badge_desk_print`: what to print.")


class OfflineRosterEventSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()


class OfflineRosterResponseSerializer(serializers.Serializer):
    lease_token = serializers.CharField()
    lease_id = serializers.UUIDField()
    server_time = serializers.DateTimeField()
    issued_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    scan_opens_at = serializers.DateTimeField()
    scan_closes_at = serializers.DateTimeField()
    sync_deadline = serializers.DateTimeField()
    event = OfflineRosterEventSerializer()
    registrations = OfflineRosterRegistrationSerializer(many=True)
    badges = BadgeDesignBundleSerializer(required=False, help_text="With `events.badge_desk_print`: the published "
                                         "badge per role and the logos, for printing with the network down.")


class OfflineCheckInResultSerializer(serializers.Serializer):
    operation_id = serializers.UUIDField()
    outcome = serializers.ChoiceField(
        choices=[
            "applied",
            "duplicate_operation",
            "already_attended",
            "registration_changed",
            "event_unavailable",
            "invalid_token",
            "outside_window",
            "stage_incomplete",
            "guardian_consent_required",
            "guardian_consent_expired",
            "guardian_terms_missing",
            "minor_not_admitted",
            "minor_below_minimum_age",
        ]
    )
    registration_id = serializers.IntegerField(required=False)
    attended_at = serializers.DateTimeField(required=False)


class OfflineCheckInSyncResponseSerializer(serializers.Serializer):
    recorded_at = serializers.DateTimeField()
    results = OfflineCheckInResultSerializer(many=True)
    badge_receipts = BadgeReceiptResultSerializer(required=False)
