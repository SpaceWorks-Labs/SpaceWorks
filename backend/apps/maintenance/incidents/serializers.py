"""Serializers for the incident register (staff and the member's own reports)."""

from rest_framework import serializers

from .models import Incident, IncidentAction


def _name(user):
    return (getattr(user, "display_name", "") or user.get_full_name() or user.username) if user else ""


class IncidentActionSerializer(serializers.ModelSerializer):
    assignee_name = serializers.SerializerMethodField()

    class Meta:
        model = IncidentAction
        fields = ["id", "description", "assignee", "assignee_name", "due_date", "done_at", "created_at"]
        read_only_fields = fields

    def get_assignee_name(self, obj):
        return _name(obj.assignee)


class IncidentSerializer(serializers.ModelSerializer):
    """The staff reading: every field, with the follow-up actions."""

    reporter_name = serializers.SerializerMethodField()
    involved_name = serializers.SerializerMethodField()
    actions = IncidentActionSerializer(many=True, read_only=True)

    class Meta:
        model = Incident
        fields = ["id", "makerspace", "kind", "severity", "status", "area", "title", "description", "location",
                  "occurred_at", "reporter", "reporter_name", "involved_user", "involved_name", "involved_note",
                  "sponsor_user", "machine", "room", "event", "loan", "booking", "repair_issue", "guest_pass",
                  "triaged_by", "resolution_note", "closed_at", "created_at", "updated_at", "actions"]
        read_only_fields = fields

    def get_reporter_name(self, obj):
        return _name(obj.reporter)

    def get_involved_name(self, obj):
        return _name(obj.involved_user) or obj.involved_note


class IncidentPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = IncidentSerializer(many=True)


class MemberIncidentSerializer(serializers.ModelSerializer):
    """What a reporter sees of their own report: no triage notes, assignees or sponsor."""

    class Meta:
        model = Incident
        fields = ["id", "kind", "severity", "status", "area", "title", "description", "location", "occurred_at",
                  "machine", "room", "event", "loan", "booking", "created_at"]
        read_only_fields = fields


class MemberIncidentPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = MemberIncidentSerializer(many=True)


class _LinkFields(serializers.Serializer):
    machine_id = serializers.IntegerField(required=False, allow_null=True)
    room_id = serializers.IntegerField(required=False, allow_null=True)
    event_id = serializers.IntegerField(required=False, allow_null=True)
    loan_id = serializers.IntegerField(required=False, allow_null=True)
    booking_id = serializers.IntegerField(required=False, allow_null=True)


class MemberIncidentReportSerializer(_LinkFields):
    kind = serializers.ChoiceField(choices=Incident.Kind.choices, default=Incident.Kind.INCIDENT)
    severity = serializers.ChoiceField(choices=Incident.Severity.choices, default=Incident.Severity.LOW)
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="", max_length=5000)
    location = serializers.CharField(required=False, allow_blank=True, default="", max_length=200)
    occurred_at = serializers.DateTimeField(required=False)


class StaffIncidentCreateSerializer(MemberIncidentReportSerializer):
    area = serializers.ChoiceField(choices=Incident.Area.choices, required=False)
    involved_user_id = serializers.IntegerField(required=False, allow_null=True)
    involved_note = serializers.CharField(required=False, allow_blank=True, max_length=200)
    sponsor_user_id = serializers.IntegerField(required=False, allow_null=True)
    repair_issue_id = serializers.IntegerField(required=False, allow_null=True)
    guest_pass_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)


class StaffIncidentUpdateSerializer(StaffIncidentCreateSerializer):
    status = serializers.ChoiceField(choices=Incident.Status.choices, required=False)
    resolution_note = serializers.CharField(required=False, allow_blank=True, max_length=5000)
    # Used with partial=True: only the fields sent change.


class IncidentActionCreateSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=300)
    assignee_id = serializers.IntegerField(required=False, allow_null=True)
    due_date = serializers.DateField(required=False, allow_null=True)


class IncidentActionUpdateSerializer(serializers.Serializer):
    done = serializers.BooleanField()
