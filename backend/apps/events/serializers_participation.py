"""Payloads and response shapes for lane L21a's participation routes (switches, attendance, crew, lists)."""
from django.utils.translation import gettext
from rest_framework import serializers

from .hackathons.admission_inputs import LiteralBoolean, StrictSerializer


class ParticipationSettingsSerializer(StrictSerializer):
    stage_advanced_email = LiteralBoolean(required=False)
    attendance_free_on_no = LiteralBoolean(required=False)
    crew_signup_open = LiteralBoolean(required=False)
    crew_approval_required = LiteralBoolean(required=False)
    crew_public_section = LiteralBoolean(required=False)


class AttendanceSendInput(StrictSerializer):
    kind = serializers.ChoiceField(choices=["confirmation", "reminder"])


class AttendanceRoundSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    kind = serializers.CharField()
    state = serializers.CharField()
    recipients = serializers.IntegerField()
    sent = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class AttendanceSummarySerializer(serializers.Serializer):
    asked = serializers.IntegerField()
    yes = serializers.IntegerField()
    no = serializers.IntegerField()
    pending = serializers.IntegerField()
    released = serializers.IntegerField()
    left_to_staff = serializers.IntegerField()
    next_send_at = serializers.DateTimeField(allow_null=True)
    free_on_no = serializers.BooleanField()
    rounds = AttendanceRoundSerializer(many=True)


class AttendanceReplyInput(StrictSerializer):
    answer = serializers.ChoiceField(choices=["yes", "no"])
    note = serializers.CharField(max_length=1000, allow_blank=True, required=False, default="")


class OwnAttendanceSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    event_title = serializers.CharField()
    starts_at = serializers.DateTimeField()
    registration_id = serializers.IntegerField()
    answer = serializers.CharField(allow_null=True)
    note = serializers.CharField()
    replied_at = serializers.DateTimeField(allow_null=True)
    effect = serializers.CharField()
    free_on_no = serializers.BooleanField()


class ReacceptResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()
    payment_due = serializers.BooleanField()


class CrewAddInput(StrictSerializer):
    member_id = serializers.IntegerField(min_value=1)
    crew_role = serializers.CharField(max_length=60, allow_blank=True, required=False, default="")


class CrewDecisionInput(StrictSerializer):
    approve = LiteralBoolean()
    expected_version = serializers.IntegerField(min_value=1)


class CrewSignupInput(StrictSerializer):
    crew_role = serializers.CharField(max_length=60, allow_blank=True, required=False, default="")
    dietary = serializers.CharField(max_length=300, allow_blank=True, required=False, default="")
    notes = serializers.CharField(max_length=1000, allow_blank=True, required=False, default="")
    show_publicly = LiteralBoolean(required=False, default=False)


class CrewRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    version = serializers.IntegerField()
    member_id = serializers.IntegerField()
    name = serializers.CharField()
    crew_role = serializers.CharField()
    state = serializers.CharField()
    origin = serializers.CharField()
    show_publicly = serializers.BooleanField()
    registration_id = serializers.IntegerField(allow_null=True)
    has_place = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    decided_at = serializers.DateTimeField(allow_null=True)


class CrewOwnSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    version = serializers.IntegerField()
    crew_role = serializers.CharField()
    state = serializers.CharField()
    show_publicly = serializers.BooleanField()
    registration_id = serializers.IntegerField(allow_null=True)


class CrewSignupStateSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    event_title = serializers.CharField()
    starts_at = serializers.DateTimeField()
    open = serializers.BooleanField()
    approval_required = serializers.BooleanField()
    crew = CrewOwnSerializer(allow_null=True)


class CateringNeedSerializer(serializers.Serializer):
    label = serializers.CharField()
    count = serializers.IntegerField()


class CateringSerializer(serializers.Serializer):
    approved = serializers.IntegerField()
    with_needs = serializers.IntegerField()
    needs = CateringNeedSerializer(many=True)


class PublicCrewSerializer(serializers.Serializer):
    handle = serializers.CharField()
    display_name = serializers.CharField()
    crew_role = serializers.CharField()


class CheckInListInput(StrictSerializer):
    name = serializers.CharField(max_length=100, required=False)
    kind = serializers.ChoiceField(choices=["swag", "meal", "workshop", "other"], required=False)
    after_entry = LiteralBoolean(required=False)
    addon_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    per_person = serializers.IntegerField(min_value=1, max_value=20, required=False)
    archive = LiteralBoolean(required=False)


class CheckInListSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    name = serializers.CharField()
    kind = serializers.CharField()
    after_entry = serializers.BooleanField()
    addon_id = serializers.IntegerField(allow_null=True)
    addon_name = serializers.CharField(allow_null=True)
    per_person = serializers.IntegerField()
    archived = serializers.BooleanField()
    archived_at = serializers.DateTimeField(allow_null=True)
    collected = serializers.IntegerField()


class CheckInListScanInput(StrictSerializer):
    operation_id = serializers.UUIDField()
    registration_id = serializers.IntegerField(min_value=1, required=False)
    token = serializers.UUIDField(required=False)

    def validate(self, attrs):
        if ("registration_id" in attrs) == ("token" in attrs):
            raise serializers.ValidationError(gettext("Choose a registration or a ticket code."))
        return attrs


class CheckInListEligibilitySerializer(serializers.Serializer):
    registration_id = serializers.IntegerField()
    name = serializers.CharField()
    allowed = serializers.IntegerField()
    used = serializers.IntegerField()
    reason = serializers.CharField(allow_null=True)
