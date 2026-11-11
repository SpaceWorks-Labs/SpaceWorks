"""Response shapes for the wider platform insights (parity E-B8). Counts and closed labels only."""

from rest_framework import serializers


class InsightsRecentBroadcastSerializer(serializers.Serializer):
    completed_at = serializers.DateTimeField()
    audience_statuses = serializers.ListField(child=serializers.CharField())
    audience_attendance = serializers.CharField()


class InsightsActivitySerializer(serializers.Serializer):
    events_held = serializers.IntegerField(min_value=0)
    registrations = serializers.IntegerField(min_value=0)
    check_ins = serializers.IntegerField(min_value=0)
    feedback_responses = serializers.IntegerField(min_value=0)
    broadcasts_sent = serializers.IntegerField(min_value=0)
    recent_broadcasts = InsightsRecentBroadcastSerializer(many=True)


class InsightsLoginMethodSerializer(serializers.Serializer):
    method = serializers.CharField()
    accounts = serializers.IntegerField(min_value=0)


class InsightsSensitiveActionSerializer(serializers.Serializer):
    action = serializers.CharField()
    count = serializers.IntegerField(min_value=0)


class InsightsApiClientLifecycleSerializer(serializers.Serializer):
    active = serializers.IntegerField(min_value=0)
    revoked = serializers.IntegerField(min_value=0)
    rotating = serializers.IntegerField(min_value=0, help_text="Active clients still inside a secret-rotation grace window.")
    unused_in_window = serializers.IntegerField(min_value=0)


class InsightsSecuritySerializer(serializers.Serializer):
    accounts_unverified = serializers.IntegerField(min_value=0)
    accounts_with_passkey = serializers.IntegerField(min_value=0)
    login_methods = InsightsLoginMethodSerializer(many=True)
    sensitive_actions = InsightsSensitiveActionSerializer(many=True)
    api_clients = InsightsApiClientLifecycleSerializer()


class InsightsStorageSerializer(serializers.Serializer):
    total_bytes = serializers.IntegerField(min_value=0)
    spaces = serializers.IntegerField(min_value=0)
    largest_bytes = serializers.ListField(child=serializers.IntegerField(min_value=0))
