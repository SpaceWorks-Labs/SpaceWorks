from django.utils.translation import gettext
from rest_framework import serializers
from apps.events.contributions.serializers import AggregateSerializer, CommandSerializer, StrictSerializer


class ZoneSerializer(StrictSerializer):
    table = serializers.CharField(max_length=40, required=False)
    zone = serializers.CharField(max_length=40, required=False)


class HelpCreateSerializer(CommandSerializer):
    # Omit for a drop-in request on an event without hackathon teams (#128 C-36, E2-f).
    team_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    type_key = serializers.SlugField(max_length=40)
    summary = serializers.CharField(max_length=2000)
    zone = ZoneSerializer(required=False)
    practice_run_id = serializers.UUIDField(required=False, allow_null=True)


class CommentInputSerializer(CommandSerializer):
    body = serializers.CharField(max_length=2000)


class ResolveInputSerializer(CommandSerializer):
    resolution_note = serializers.CharField(max_length=2000)


class ReopenInputSerializer(CommandSerializer):
    reason = serializers.CharField(max_length=2000)


class AssignHelpSerializer(ReopenInputSerializer):
    mentor_assignment_id = serializers.IntegerField(min_value=1)


class HelpSerializer(AggregateSerializer):
    state = serializers.ChoiceField(choices=["open", "claimed", "resolved", "cancelled", "expired"])
    origin = serializers.ChoiceField(choices=["team", "mentor", "round", "attendee"], required=False)
    team_id = serializers.IntegerField(required=False, allow_null=True)
    team_alias = serializers.CharField(required=False)
    category = serializers.CharField(required=False)
    priority = serializers.IntegerField(required=False)
    zone = ZoneSerializer(required=False)
    summary = serializers.CharField(required=False)
    raised_by_role_assignment_id = serializers.IntegerField(required=False, allow_null=True)
    claim_released = serializers.BooleanField(required=False)
    position = serializers.IntegerField(required=False, allow_null=True)
    available_mentors = serializers.IntegerField(required=False)
    wait_estimate = serializers.CharField(required=False)
    claim_uuid = serializers.UUIDField(allow_null=True, required=False)
    claim_generation = serializers.IntegerField(required=False)
    claim_expires_at = serializers.DateTimeField(allow_null=True, required=False)
    expires_at = serializers.DateTimeField(required=False)
    organizer_contact_action = serializers.CharField(required=False)


class CommentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    help_id = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    body = serializers.CharField()
    origin = serializers.ChoiceField(choices=["team", "mentor"])
    request_version = serializers.IntegerField()


class BookingInputSerializer(CommandSerializer):
    # Omit for a drop-in booking on an event without hackathon teams (#128 C-36, E2-f).
    team_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class BookingSerializer(AggregateSerializer):
    state = serializers.ChoiceField(choices=["booked", "cancelled"])
    team_id = serializers.IntegerField(allow_null=True)
    slot_id = serializers.IntegerField()


class ManualAssignmentSerializer(StrictSerializer):
    team_id = serializers.IntegerField(min_value=1)
    mentor_assignment_id = serializers.IntegerField(min_value=1)


class AssignmentInputSerializer(CommandSerializer):
    team_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), min_length=1, max_length=500)
    mode = serializers.ChoiceField(choices=["manual", "round_robin", "skill_match"])
    skill_weights = serializers.DictField(child=serializers.IntegerField(min_value=1, max_value=100), default=dict)
    manual = ManualAssignmentSerializer(many=True, max_length=500, default=list)

    def validate(self, attrs):
        ids = attrs["team_ids"]
        manual_ids = [row["team_id"] for row in attrs["manual"]]
        if len(ids) != len(set(ids)) or len(manual_ids) != len(set(manual_ids)):
            raise serializers.ValidationError(gettext("Team IDs must be distinct."))
        if set(manual_ids) - set(ids) or (attrs["mode"] == "manual" and set(manual_ids) != set(ids)):
            raise serializers.ValidationError({"manual": gettext("Map every selected team exactly once in manual mode.")})
        return attrs


class AssignmentPreviewSerializer(serializers.Serializer):
    assignments = ManualAssignmentSerializer(many=True)
    unsatisfied_team_ids = serializers.ListField(child=serializers.IntegerField())


class AssignmentDecisionSerializer(ManualAssignmentSerializer):
    id = serializers.IntegerField()
    version = serializers.IntegerField()
    state = serializers.ChoiceField(choices=["active", "proposed"])


class AssignmentRunSerializer(AggregateSerializer):
    run_id = serializers.UUIDField()
    assignments = AssignmentDecisionSerializer(many=True)
    unsatisfied_team_ids = serializers.ListField(child=serializers.IntegerField())


class AssignmentMappingSerializer(AggregateSerializer):
    mentor_assignment_id = serializers.IntegerField()
    team_id = serializers.IntegerField()
    mode = serializers.CharField()
    active_from = serializers.DateTimeField()
    ended_at = serializers.DateTimeField(allow_null=True)
    run_id = serializers.UUIDField()


class RoundWriteSerializer(CommandSerializer):
    index = serializers.IntegerField(min_value=1, max_value=100, required=False)
    key = serializers.SlugField(max_length=40, required=False)
    label = serializers.CharField(max_length=100, required=False)
    opens_at = serializers.DateTimeField(required=False)
    closes_at = serializers.DateTimeField(required=False)
    form_schema = serializers.DictField(required=False)
    note_keys = serializers.ListField(child=serializers.CharField(max_length=80), max_length=50, required=False)
    rating_keys = serializers.ListField(child=serializers.CharField(max_length=80), max_length=50, required=False)
    allow_fresh_eyes_override = serializers.BooleanField(required=False)
    allow_conflict_override = serializers.BooleanField(required=False)
    practice_run_id = serializers.UUIDField(required=False, allow_null=True)
    help_trigger_rules = serializers.ListField(child=serializers.DictField(), max_length=10, required=False)


class RoundSerializer(AggregateSerializer):
    index = serializers.IntegerField()
    key = serializers.CharField()
    label = serializers.CharField()
    opens_at = serializers.DateTimeField()
    closes_at = serializers.DateTimeField()
    form_schema = serializers.JSONField()
    note_keys = serializers.ListField(child=serializers.CharField())
    teams = serializers.ListField(child=serializers.DictField(), required=False)
    next_team_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    rating_keys = serializers.ListField(child=serializers.CharField())
    allow_fresh_eyes_override = serializers.BooleanField()
    allow_conflict_override = serializers.BooleanField()
    practice_run_id = serializers.UUIDField(allow_null=True)
    help_trigger_rules = serializers.JSONField()


class ClaimInputSerializer(CommandSerializer):
    override_reason = serializers.CharField(max_length=2000, required=False)


class LeaseInputSerializer(CommandSerializer):
    lease_uuid = serializers.UUIDField()
    generation = serializers.IntegerField(min_value=1)


class RoundSubmitSerializer(LeaseInputSerializer):
    answers = serializers.DictField()
    away = serializers.BooleanField(default=False)
    override_reason = serializers.CharField(max_length=2000, required=False)
    nominate = serializers.BooleanField(default=False)


class LeaseSerializer(AggregateSerializer):
    lease_uuid = serializers.UUIDField()
    generation = serializers.IntegerField()
    expires_at = serializers.DateTimeField()
    heartbeat_at = serializers.DateTimeField()
    team_id = serializers.IntegerField()
    round_id = serializers.IntegerField()
