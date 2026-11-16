from rest_framework import serializers
from apps.events.contributions.serializers import CommandSerializer, WindowSerializer, AggregateSerializer


class MentorProfileWriteSerializer(CommandSerializer):
    skills = serializers.ListField(child=serializers.SlugField(max_length=40), max_length=50, required=False)
    affiliation = serializers.CharField(max_length=2000, allow_blank=True, required=False)
    availability = WindowSerializer(many=True, max_length=50, required=False)
    max_active_teams = serializers.IntegerField(min_value=1, max_value=100, required=False)


class MentorProfileSerializer(AggregateSerializer):
    assignment_id = serializers.IntegerField()
    skills = serializers.ListField(child=serializers.CharField())
    affiliation = serializers.CharField()
    availability = serializers.JSONField()
    max_active_teams = serializers.IntegerField()


class HelpTypeWriteSerializer(CommandSerializer):
    key = serializers.SlugField(max_length=40, required=False)
    label = serializers.CharField(max_length=100, required=False)
    skill_tags = serializers.ListField(child=serializers.SlugField(max_length=40), max_length=50, required=False)
    priority = serializers.IntegerField(min_value=0, max_value=100, required=False)
    open_limit = serializers.IntegerField(min_value=1, max_value=10, required=False)
    claim_minutes = serializers.IntegerField(min_value=1, max_value=60, required=False)
    expiry_minutes = serializers.IntegerField(min_value=15, max_value=10080, required=False)
    organizer_contact_action = serializers.CharField(max_length=300, allow_blank=True, required=False)


class HelpTypeSerializer(AggregateSerializer):
    key = serializers.CharField()
    label = serializers.CharField()
    skill_tags = serializers.ListField(child=serializers.CharField())
    priority = serializers.IntegerField()
    open_limit = serializers.IntegerField()
    claim_minutes = serializers.IntegerField()
    expiry_minutes = serializers.IntegerField()
    organizer_contact_action = serializers.CharField()


class ConflictWriteSerializer(CommandSerializer):
    mentor_assignment_id = serializers.IntegerField(min_value=1)
    team_id = serializers.IntegerField(min_value=1)
    kind = serializers.ChoiceField(choices=["declared", "affiliation"])
    active = serializers.BooleanField(default=True)
    reason = serializers.CharField(max_length=2000)


class ConflictSerializer(AggregateSerializer):
    mentor_assignment_id = serializers.IntegerField()
    team_id = serializers.IntegerField()
    kind = serializers.CharField()
    active = serializers.BooleanField()
    reason = serializers.CharField()


class MuteSerializer(CommandSerializer):
    minutes = serializers.IntegerField(min_value=0, max_value=120)


class MuteResultSerializer(AggregateSerializer):
    muted_until = serializers.DateTimeField(allow_null=True)


class NominationSerializer(CommandSerializer):
    team_id = serializers.IntegerField(min_value=1)


class RenewHelpSerializer(CommandSerializer):
    claim_uuid = serializers.UUIDField()
    claim_generation = serializers.IntegerField(min_value=1)
