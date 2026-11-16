from django.utils.translation import gettext
from rest_framework import serializers
from .serializers import CommandSerializer, StrictSerializer


class PostingWriteSerializer(CommandSerializer):
    role = serializers.ChoiceField(choices=["volunteer", "mentor"], required=False)
    title = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(max_length=10000, allow_blank=True, required=False)
    briefing = serializers.CharField(max_length=10000, allow_blank=True, required=False)
    skills = serializers.ListField(child=serializers.SlugField(max_length=40), max_length=50, required=False)
    visibility = serializers.ChoiceField(choices=["public", "members", "audience_organizations"], required=False)
    approval_required = serializers.BooleanField(required=False)
    opens_at = serializers.DateTimeField(required=False)
    closes_at = serializers.DateTimeField(required=False)
    permission_preset = serializers.ListField(child=serializers.CharField(max_length=40), max_length=20, required=False)
    form_schema = serializers.DictField(required=False)
    requirements = serializers.DictField(required=False)
    state = serializers.ChoiceField(choices=["draft", "open", "closed"], required=False)


class ShiftWriteSerializer(CommandSerializer):
    posting_id = serializers.IntegerField(min_value=1, required=False)
    kind = serializers.ChoiceField(choices=["volunteer", "office_hours"], required=False)
    mentor_assignment_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    starts_at = serializers.DateTimeField(required=False)
    ends_at = serializers.DateTimeField(required=False)
    signup_deadline = serializers.DateTimeField(required=False)
    task = serializers.CharField(max_length=200, required=False)
    zone = serializers.CharField(max_length=100, allow_blank=True, required=False)
    capacity = serializers.IntegerField(min_value=0, required=False)
    grace_minutes = serializers.IntegerField(min_value=0, max_value=60, required=False)
    waitlist_enabled = serializers.BooleanField(required=False)
    approval_required = serializers.BooleanField(required=False)
    requirements = serializers.DictField(required=False)
    permission_preset = serializers.ListField(child=serializers.CharField(max_length=40), max_length=20, required=False)
    state = serializers.ChoiceField(choices=["open", "closed"], required=False)
    cancel_bookings = serializers.BooleanField(required=False)
    reason = serializers.CharField(max_length=2000, required=False)


class AdminRoleSerializer(CommandSerializer):
    member_id = serializers.IntegerField(min_value=1, required=False)
    posting_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    sponsor_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    role = serializers.ChoiceField(choices=["co_organizer", "volunteer", "mentor", "judge", "sponsor_rep"], required=False)
    display_on_page = serializers.BooleanField(required=False)
    delegated_permissions = serializers.ListField(child=serializers.CharField(max_length=40), max_length=20, required=False)
    track_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=50, required=False)


class AdminAttendanceSerializer(CommandSerializer):
    occurred_at = serializers.DateTimeField(required=False)
    break_minutes = serializers.IntegerField(min_value=0, max_value=1440, required=False)
    reason = serializers.CharField(max_length=2000, required=False)


def requirements(value):
    # Age/guardian settings have no vocabulary here, even when nested in JSON.
    permitted = {"training_ids", "briefing_ids", "host_waiver_required"}
    if set(value) - permitted:
        raise serializers.ValidationError({"requirements": gettext("Unknown requirement.")})
    for key in ("training_ids", "briefing_ids"):
        if key in value and (not isinstance(value[key], list) or len(value[key]) > 50 or any(
                type(x) is not int or x < 1 for x in value[key])):
            raise serializers.ValidationError({"requirements": gettext("Use bounded positive reference IDs.")})
    if "host_waiver_required" in value and type(value["host_waiver_required"]) is not bool:
        raise serializers.ValidationError({"requirements": gettext("Use a boolean waiver requirement.")})
    return value
