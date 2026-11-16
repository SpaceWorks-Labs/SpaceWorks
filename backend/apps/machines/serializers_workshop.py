"""Serializers for induction events and supervised workshop sessions (decision 223)."""

from rest_framework import serializers

from .models import EventInductionLink, SupervisedParticipant, SupervisedSession, SupervisedUse


def _name(user):
    return (getattr(user, "display_name", "") or user.get_full_name() or user.username) if user else ""


class InductionLinkCreateSerializer(serializers.Serializer):
    certification_type_id = serializers.IntegerField()


class InductionLinkSerializer(serializers.ModelSerializer):
    certification_type_name = serializers.CharField(source="certification_type.name", read_only=True)
    machine_type_id = serializers.IntegerField(source="certification_type.machine_type_id", read_only=True)

    class Meta:
        model = EventInductionLink
        fields = ["id", "event", "certification_type", "certification_type_name", "machine_type_id", "created_at"]
        read_only_fields = fields


class InductionAttendeeSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    name = serializers.CharField()
    is_member = serializers.BooleanField()
    certified_type_ids = serializers.ListField(child=serializers.IntegerField())


class InductionOverviewSerializer(serializers.Serializer):
    links = InductionLinkSerializer(many=True)
    attendees = InductionAttendeeSerializer(many=True)
    can_grant = serializers.BooleanField()


class InductionGrantSerializer(serializers.Serializer):
    user_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False, max_length=500)
    certification_type_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=False)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


class InductionGrantResultSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    certification_type_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=["granted", "already_certified", "refused"])
    grant_id = serializers.IntegerField(required=False, allow_null=True)
    guest = serializers.BooleanField(required=False)
    code = serializers.CharField(required=False)


class InductionGrantResponseSerializer(serializers.Serializer):
    results = InductionGrantResultSerializer(many=True)


class GuestGrantRevokeSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class SupervisedSessionOpenSerializer(serializers.Serializer):
    event_id = serializers.IntegerField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, max_length=300, default="")


class SupervisedSuperviseeSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()


class SupervisedUseStartSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    note = serializers.CharField(required=False, allow_blank=True, max_length=300, default="")


class SupervisedActionSerializer(serializers.Serializer):
    """Close and end take no fields; naming the serializer keeps strays refused, not ignored."""


class SupervisedParticipantSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = SupervisedParticipant
        fields = ["user", "name", "added_at", "removed_at"]
        read_only_fields = fields

    def get_name(self, obj):
        return _name(obj.user)


class SupervisedUseSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupervisedUse
        fields = ["id", "user", "instructor", "started_at", "ended_at", "note"]
        read_only_fields = fields


class SupervisedSessionSerializer(serializers.ModelSerializer):
    machine_name = serializers.CharField(source="machine.name", read_only=True)
    instructor_name = serializers.SerializerMethodField()
    participants = SupervisedParticipantSerializer(many=True, read_only=True)
    uses = SupervisedUseSerializer(many=True, read_only=True)
    is_open = serializers.BooleanField(read_only=True)

    class Meta:
        model = SupervisedSession
        fields = ["id", "makerspace", "machine", "machine_name", "instructor", "instructor_name", "event", "note",
                  "opened_at", "closed_at", "is_open", "participants", "uses"]
        read_only_fields = fields

    def get_instructor_name(self, obj):
        return _name(obj.instructor)


class SupervisedSessionPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = SupervisedSessionSerializer(many=True)
